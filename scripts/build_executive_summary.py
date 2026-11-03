"""Generate the one-page brief and three analytical figures from computed exports."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parents[1]
TEAL, SLATE = "#087F8C", "#60758D"


def main():
    font_dir = Path("/usr/share/fonts/truetype/dejavu")
    if font_dir.exists():
        pdfmetrics.registerFont(TTFont("Body", str(font_dir / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("Heading", str(font_dir / "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFontFamily("Body", normal="Body", bold="Heading")
    else:
        # Portable fallback when rebuilding on a machine without DejaVu.
        pdfmetrics.registerFont(pdfmetrics.Font("Body", "Helvetica", "WinAnsiEncoding"))
        pdfmetrics.registerFont(pdfmetrics.Font("Heading", "Helvetica-Bold", "WinAnsiEncoding"))
        pdfmetrics.registerFontFamily("Body", normal="Body", bold="Heading")
    reports = ROOT / "reports"
    metrics = json.loads((reports / "analysis.json").read_text())
    findings = json.loads((reports / "findings.json").read_text())
    states = pd.read_csv(reports / "state_diagnostics.csv").set_index("customer_state")
    rates = pd.read_csv(reports / "handoff_rates.csv")
    output = ROOT / "docs/figures"
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": "#24364B",
            "text.color": "#24364B",
            "axes.titleweight": "bold",
        }
    )
    # Each figure is standalone for README reuse; these are computed charts, not screenshots.
    images = []
    fig, ax = plt.subplots(figsize=(5.4, 3.4), layout="constrained")
    ax.bar(rates.handoff, rates.late_rate * 100, color=[SLATE, TEAL])
    for i, row in rates.iterrows():
        ax.text(
            i,
            row.late_rate * 100 + 0.6,
            f"{row.late_rate:.1%}\n{row.late_orders:,.0f}/{row.orders:,}",
            ha="center",
            fontsize=10,
        )
    ax.set(ylim=(0, 28), ylabel="Late deliveries (%)", title="Handoff: compare rates, not counts")
    fig.savefig(output / "handoff_rates.png", dpi=180)
    images.append(output / "handoff_rates.png")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(5.4, 3.4), layout="constrained")
    vals = states.loc[["SP", "RJ"]]
    ax.barh(vals.index, vals.late_rate * 100, color=[SLATE, TEAL])
    for i, (state, row) in enumerate(vals.iterrows()):
        ax.text(
            row.late_rate * 100 + 0.2,
            i,
            f"{row.late_rate:.2%}\n{row.late_orders:,.0f}/{row.known_deliveries:,.0f}",
            va="center",
            fontsize=10,
        )
    ax.set(xlim=(0, 17), xlabel="Late deliveries (%)", title="Regional reliability: SP and RJ")
    fig.savefig(output / "regional_rates.png", dpi=180)
    images.append(output / "regional_rates.png")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(5.4, 3.4), layout="constrained")
    diffs = findings["retention_differences"]
    point = np.array([d["difference_pp"] for d in diffs])
    low = np.array([d["ci95_pp"][0] for d in diffs])
    high = np.array([d["ci95_pp"][1] for d in diffs])
    ax.errorbar(point, [1, 0], xerr=[point - low, high - point], fmt="o", capsize=6, color=TEAL)
    ax.axvline(0, color=SLATE, linestyle="--", linewidth=1)
    ax.set(
        yticks=[1, 0],
        yticklabels=["After delivery", "Including pre-delivery"],
        ylim=(-0.65, 1.65),
        xlim=(-0.8, 0.45),
        xlabel="Late minus on-time repeat rate (pp)",
        title="Retention gap: 95% intervals",
    )
    fig.savefig(output / "retention_gap.png", dpi=180)
    images.append(output / "retention_gap.png")
    plt.close(fig)
    page = ROOT / "docs/executive_summary.pdf"
    pdf = canvas.Canvas(str(page), pagesize=A4)
    width, height = A4
    pdf.setFillColor(colors.HexColor("#14283F"))
    pdf.rect(0, height - 105, width, 105, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Heading", 21)
    pdf.drawString(36, height - 42, "Where should delivery teams act?")
    pdf.setFont("Body", 10)
    pdf.drawString(
        36,
        height - 65,
        f"Olist operating review | Historical purchase cohorts through {metrics['cutoff']}",
    )
    pdf.drawString(
        36,
        height - 83,
        f"{metrics['delivered_orders']:,} delivered orders | BRL {metrics['gmv_brl'] / 1e6:.2f}M merchandise value | Observational analysis",
    )
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "Body"
    styles["Normal"].fontSize = 9
    styles["Normal"].leading = 12

    def para(text, x, y, w):
        p = Paragraph(text, styles["Normal"])
        _, h = p.wrap(w, 150)
        p.drawOn(pdf, x, y - h)
        return h

    row_y = height - 125
    titles = ["1  Seller handoff", "2  Regional delivery", "3  Retention sensitivity"]
    h = rates.set_index("handoff").loc["Late"]
    estimate = findings["retention_differences"][0]
    distance = findings["rj_distance_scenario"]
    texts = [
        f"Late handoff is {h.order_share:.1%} of eligible orders but {h.late_order_share:.1%} of late orders. Its late-delivery rate is {findings['handoff_rate_ratio']:.2f}x the timely group.",
        f"RJ: {states.loc['RJ', 'late_rate']:.2%} late versus SP: {states.loc['SP', 'late_rate']:.2%}. Standardizing non-RJ distance-band rates to {distance['eligible_rj_orders']:,} eligible RJ orders gives a comparison of {findings['rj_distance_scenario']['fewer_late']:,.0f} fewer late orders.",
        f"Equal follow-up: {estimate['late_repeat']:,}/{estimate['late_n']:,} late customers repeated versus {estimate['on_time_repeat']:,}/{estimate['on_time_n']:,} on time. The broader definition includes a longer exposure window and its interval crosses zero.",
    ]
    for i in range(3):
        y = row_y - i * 173
        pdf.setFillColor(colors.HexColor("#14283F"))
        pdf.setFont("Heading", 12)
        pdf.drawString(36, y, titles[i])
        pdf.drawImage(
            ImageReader(str(images[i])),
            30,
            y - 157,
            width=280,
            height=136,
            preserveAspectRatio=True,
            mask="auto",
        )
        para(texts[i], 325, y - 20, 230)
    y = height - 665
    pdf.setFont("Heading", 12)
    pdf.drawString(36, y, "Actions to validate")
    para(
        "1. Audit late handoffs and carrier tracking events before assigning responsibility.<br/>2. Compare RJ routes, delivery promises and order mix within distance bands.<br/>3. Test service recovery with a randomized holdout and a fixed 90-day outcome.",
        36,
        y - 10,
        width - 72,
    )
    para(
        "<b>Limits:</b> Handoff and distance are proxies. Scenarios are not avoidable orders or upper bounds. Retention intervals use an independent-proportion normal approximation. The late-delivery primary group has relatively few repeat events. No business uplift or manual time saving has been measured.",
        36,
        84,
        width - 72,
    )
    pdf.setFont("Body", 7)
    pdf.drawString(
        36,
        22,
        "Source: Olist public dataset; reports/findings.json, handoff_rates.csv and state_diagnostics.csv.",
    )
    pdf.save()
    print(page)


if __name__ == "__main__":
    main()
