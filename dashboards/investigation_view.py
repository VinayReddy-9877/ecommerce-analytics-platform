"""Decision-focused delivery review, rendered from pipeline exports."""

import json

import pandas as pd
import plotly.express as px
import streamlit as st


def chart(fig):
    fig.update_layout(height=300)
    st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False})


def render(root):
    reports = root / "reports"
    required = [
        "deepdive.json",
        "analysis.json",
        "state_diagnostics.csv",
        "daily_sales.csv",
        "retention_sensitivity.csv",
    ]
    missing = [name for name in required if not (reports / name).exists()]
    st.title("Delivery reliability & customer retention")
    if missing:
        st.info(
            "Run `olist run`, then `olist deepdive` to generate this review. Missing: "
            + ", ".join(missing)
        )
        return
    d = json.loads((reports / "deepdive.json").read_text())
    metrics = json.loads((reports / "analysis.json").read_text())
    status = reports / "last_run.json"
    if status.exists() and json.loads(status.read_text()).get("status") != "success":
        st.warning(
            "The latest pipeline run did not succeed. These exports may be from an earlier run."
        )
    st.caption(f"OPERATING REVIEW  /  Historical purchases through {metrics['cutoff']}  /  BRL")
    st.caption(
        f"Weekly comparisons and forecasts use data through {metrics['reporting_end']}. Retention uses eligible customers with sufficient follow-up."
    )
    states = pd.read_csv(reports / "state_diagnostics.csv")
    daily = pd.read_csv(reports / "daily_sales.csv")
    sensitivity = pd.read_csv(reports / "retention_sensitivity.csv")
    orders, gmv = daily.orders.sum(), daily.gmv.sum()
    known = states.known_deliveries.sum()
    late = states.late_orders.sum() / known if known else None
    cards = st.columns(4)
    cards[0].metric("Delivered orders", f"{orders:,.0f}")
    cards[1].metric("Late delivery rate", f"{late:.2%}" if late is not None else "—")
    cards[2].metric("Merchandise GMV", f"BRL {gmv / 1e6:,.2f}M")
    cards[3].metric("Average order value", f"BRL {gmv / orders:,.2f}" if orders else "—")
    st.caption(
        "Late rate uses deliveries with known timestamps. GMV covers merchandise value on delivered orders."
    )

    scenario = d.get("rj_scenario", {})
    benchmark = states[states.customer_state.isin(["RJ", "SP"])].copy()
    ratio = (
        scenario.get("rj_late_rate", 0) / scenario["sp_late_rate"]
        if scenario.get("sp_late_rate")
        else None
    )
    with st.container(border=True):
        st.subheader(
            f"RJ’s late delivery rate is {ratio:.1f}× SP’s"
            if ratio is not None
            else "Regional delivery reliability"
        )
        st.write(
            "Prioritize a review of delivery routes, carrier performance and delivery promises before attributing delays to sellers."
        )

    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("01 / Where is the reliability gap?")
        fig = px.scatter(
            benchmark,
            x="late_rate",
            y="customer_state",
            color="customer_state",
            text=benchmark.late_rate.map(lambda v: f"{v:.2%}"),
            hover_data=["known_deliveries", "late_orders"],
            color_discrete_map={"RJ": "#087F8C", "SP": "#60758D"},
        )
        fig.update_traces(marker_size=17, textposition="top center")
        fig.update_layout(
            showlegend=False, xaxis_title="Late deliveries / known deliveries", yaxis_title=None
        )
        fig.update_xaxes(tickformat=".0%", rangemode="tozero")
        chart(fig)
        st.caption(
            " · ".join(
                f"{r.customer_state}: {r.late_orders:,.0f} late / {r.known_deliveries:,.0f} known deliveries"
                for r in benchmark.itertuples()
            )
        )
    with right, st.container(border=True):
        st.subheader("02 / Late handoff is associated with higher risk")
        rates_path = reports / "handoff_rates.csv"
        if rates_path.exists():
            rates = pd.read_csv(rates_path)
            fig = px.bar(
                rates,
                x="handoff",
                y="late_rate",
                color="handoff",
                text=rates.late_rate.map(lambda v: f"{v:.1%}"),
                hover_data=["orders", "late_orders", "order_share", "late_order_share"],
                color_discrete_map={"Timely": "#60758D", "Late": "#087F8C"},
            )
            fig.update_layout(
                showlegend=False, xaxis_title="Carrier handoff", yaxis_title="Late delivery rate"
            )
            fig.update_yaxes(tickformat=".0%")
            chart(fig)
            late_handoff = rates[rates.handoff.eq("Late")].iloc[0]
            st.caption(
                f"Late handoff: {late_handoff.order_share:.1%} of eligible orders, {late_handoff.late_order_share:.1%} of late orders. Association, not seller fault."
            )
            st.caption(
                " · ".join(
                    f"{r.handoff}: {r.late_orders:,.0f}/{r.orders:,.0f}" for r in rates.itertuples()
                )
            )
        else:
            st.info("Run olist deepdive to refresh the handoff rate comparison.")

    left, right = st.columns([1.15, 1])
    with left, st.container(border=True):
        st.subheader("03 / Does the repeat-purchase definition matter?")
        labels = {
            "After first delivery": "After delivery",
            "After first purchase through delivery + 90 days": "Including pre-delivery",
        }
        sensitivity["Definition"] = sensitivity.definition.replace(labels)
        fig = px.bar(
            sensitivity,
            x="Definition",
            y="repeat_rate",
            color="experience",
            barmode="group",
            text=sensitivity.repeat_rate.map(lambda v: f"{v:.2%}"),
            hover_data=["customers", "repeat_customers"],
            color_discrete_map={"On time": "#087F8C", "Late": "#60758D"},
        )
        fig.update_layout(yaxis_title="Repeat customer rate", xaxis_title=None, legend_title=None)
        fig.update_yaxes(tickformat=".1%")
        chart(fig)
        st.caption(
            "Same eligible cohort; the broader definition adds pre-delivery purchases and therefore a longer exposure window. The association is sensitive to the outcome definition."
        )
        with st.expander("View cohort counts and definitions"):
            st.dataframe(sensitivity.drop(columns="Definition"), hide_index=True)
    with right, st.container(border=True):
        st.subheader("04 / What is the size of the opportunity?")
        st.caption("ILLUSTRATIVE SCENARIO • NOT AN ACHIEVED RESULT")
        if scenario and scenario.get("known_orders"):
            observed = scenario["late_orders"]
            expected = scenario["known_orders"] * scenario["sp_late_rate"]
            st.dataframe(
                pd.DataFrame(
                    {
                        "RJ scenario": [
                            "Observed late orders",
                            "At SP’s observed late rate",
                            "Potential fewer late orders",
                        ],
                        "Orders": [
                            f"{observed:,.0f}",
                            f"{expected:,.0f}",
                            f"{observed - expected:,.0f}",
                        ],
                    }
                ),
                hide_index=True,
                width="stretch",
            )
            st.write(
                "Assumption: SP’s observed late rate is attainable in RJ despite differences in routes, order mix and delivery promises."
            )
        else:
            st.info("RJ/SP scenario is unavailable for this dataset.")
        st.caption(
            "Do not interpret this comparison as savings, a forecast, or evidence of a causal effect."
        )

    findings_path = reports / "findings.json"
    if findings_path.exists():
        findings = json.loads(findings_path.read_text())
        with st.container(border=True):
            st.subheader("Sensitivity and comparison assumptions")
            for estimate in findings["retention_differences"]:
                lo, hi = estimate["ci95_pp"]
                st.write(
                    f"{estimate['definition']}: late minus on-time {estimate['difference_pp']:+.2f} pp (95% interval {lo:+.2f} to {hi:+.2f}); {estimate['late_repeat']}/{estimate['late_n']:,} late customers repeated."
                )
            distance = findings["rj_distance_scenario"]
            st.write(
                f"RJ distance-band benchmark: {distance['observed_late']:,} observed late orders versus {distance['expected_late']:,.0f} expected among {distance['eligible_rj_orders']:,} eligible single-seller orders. Scenario difference: {distance['fewer_late']:,.0f}."
            )
            st.caption(
                "Reference: non-RJ orders standardized to RJ’s distance bands. Different eligible population from the SP scenario; neither is a causal estimate or an upper bound. Retention intervals use a normal approximation."
            )

    with st.container(border=True):
        st.subheader("Recommended next steps")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Priority": "01",
                        "Action": "Review RJ routes and delivery promises",
                        "Validation": "Compare late rates within distance bands, purchase months and carrier routes.",
                    },
                    {
                        "Priority": "02",
                        "Action": "Audit timely-handoff orders that arrived late",
                        "Validation": "Inspect tracking events and transit durations before assigning responsibility.",
                    },
                    {
                        "Priority": "03",
                        "Action": "Test a retention intervention with a holdout",
                        "Validation": "Use a fixed 90-day outcome window; report counts and uncertainty.",
                    },
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    with st.expander("Supporting analysis and limitations"):
        st.subheader("State diagnostics")
        st.dataframe(states, hide_index=True)
        st.subheader("Distance and transit models")
        st.json(d["models"])
        st.caption(
            "Descriptive in-sample associations, not causal attribution. Late outcome uses a linear probability model."
        )
        installments = reports / "installment_behavior.csv"
        if installments.exists():
            st.subheader("Installment behavior")
            st.dataframe(pd.read_csv(installments), hide_index=True)
        st.write(
            f"{d['sellers_for_80pct_gmv']:,} of {d['seller_count']:,} sellers account for 80% of merchandise GMV."
        )
        for caveat in d["caveats"]:
            st.caption(caveat)
    st.caption(
        "SOURCE: Olist historical dataset • Observational analysis • This page uses the full exported analysis window."
    )
