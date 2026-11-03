"""Create a portable HTML review from the same exports as Streamlit."""

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
from plotly.io import to_html

ROOT = Path(__file__).resolve().parents[1]
reports = ROOT / "reports"
metrics = json.loads((reports / "analysis.json").read_text())
monthly = pd.read_csv(reports / "monthly_sales.csv")
states = pd.read_csv(reports / "delivery_performance.csv").sort_values("late_rate")
rfm = pd.read_csv(reports / "customer_rfm.csv")
segments = rfm.groupby("segment", as_index=False).monetary_value.sum()
cohorts = pd.read_csv(reports / "cohort_retention.csv")
findings = json.loads((reports / "findings.json").read_text())
rates = pd.read_csv(reports / "handoff_rates.csv")
regional = pd.read_csv(reports / "state_diagnostics.csv")
regional = regional[regional.customer_state.isin(["RJ", "SP"])]
differences = pd.DataFrame(findings["retention_differences"])
differences["lower_error"] = differences.apply(lambda r: r.difference_pp - r.ci95_pp[0], axis=1)
differences["upper_error"] = differences.apply(lambda r: r.ci95_pp[1] - r.difference_pp, axis=1)
figures = [
    px.bar(
        rates,
        x="handoff",
        y="late_rate",
        title="Late delivery rate by handoff",
        hover_data=["orders", "late_orders", "order_share", "late_order_share"],
    ),
    px.bar(
        regional,
        x="customer_state",
        y="late_rate",
        title="Regional late rate",
        hover_data=["known_deliveries", "late_orders"],
    ),
    px.scatter(
        differences,
        x="difference_pp",
        y="definition",
        error_x="upper_error",
        error_x_minus="lower_error",
        title="Retention difference: late minus on time (pp)",
        hover_data=["late_n", "late_repeat", "on_time_n", "on_time_repeat"],
    ),
    px.line(monthly, x="month", y="gmv", title="Historical delivered merchandise GMV (BRL)"),
]
for figure in figures[:2]:
    figure.update_yaxes(tickformat=".1%")
parts = []
for index, figure in enumerate(figures):
    figure.update_layout(
        template="plotly_white",
        font_family="Arial",
        margin=dict(l=40, r=20, t=60, b=55),
        height=400,
    )
    figure.update_traces(marker_color="#176b83") if index in [1, 2] else None
    parts.append(to_html(figure, full_html=False, include_plotlyjs=True if index == 0 else False))
html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Olist operating review</title>
<style>body{{margin:0;background:#edf2f5;color:#183044;font-family:Arial,sans-serif}}main{{max-width:1200px;margin:auto;padding:36px 24px}}h1{{font-size:36px;margin-bottom:10px}}.sub{{color:#536778}}.metrics,.grid{{display:grid;gap:18px;grid-template-columns:repeat(2,minmax(0,1fr))}}.metrics{{grid-template-columns:repeat(3,minmax(0,1fr));margin:28px 0}}.card{{background:white;padding:22px;border-radius:10px;overflow:hidden}}.value{{font-size:28px;font-weight:bold;margin-top:12px}}footer{{line-height:1.6;margin:28px 0}}@media(max-width:800px){{.metrics,.grid{{grid-template-columns:1fr}}}}</style></head><body><main>
<p class="sub">OLIST / HISTORICAL OPERATING REVIEW</p><h1>What the orders tell us</h1><p class="sub">Purchase cutoff {metrics["cutoff"]} · final snapshot statuses · all money in BRL</p>
<div class="metrics"><div class="card">Merchandise GMV<div class="value">R$ {metrics["gmv_brl"]:,.0f}</div></div><div class="card">Delivered orders<div class="value">{metrics["delivered_orders"]:,}</div></div><div class="card">Repeat customer share<div class="value">{metrics["repeat_customer_rate"]:.2%}</div></div></div>
<div class="grid">{"".join('<div class="card">' + part + "</div>" for part in parts)}</div>
<footer><strong>Reading the results.</strong> GMV excludes freight and is not platform revenue. Handoff rates are observational, not seller fault. Retention intervals use a normal approximation; the broader definition has longer exposure. Scenarios are not causal improvements or upper bounds. Hover charts for values and use the toolbar to export images.<br>Data: Olist Brazilian E-Commerce Public Dataset, CC BY-NC-SA 4.0. This is an independent educational analysis.</footer></main></body></html>"""
(reports / "dashboard_snapshot.html").write_text(html)
