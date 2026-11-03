"""Streamlit dashboard for sales and delivery analytics."""

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from ui_theme import apply_theme

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

st.set_page_config(
    page_title="Analytics Workspace",
    page_icon="📊",
    layout="wide",
)

apply_theme()


@st.cache_data(ttl=60)
def load(name):
    return pd.read_csv(REPORTS / f"{name}.csv")


def show_delivery():
    if not (REPORTS / "weekly_delivery_alerts.csv").exists():
        return

    alerts = load("weekly_delivery_alerts").copy()
    alerts["week"] = pd.to_datetime(alerts["week"])
    alerts = alerts[
        alerts.week + pd.Timedelta(days=6) <= pd.Timestamp(metrics["reporting_end"])
    ].sort_values("week")

    if alerts.empty:
        return

    latest = alerts.iloc[-1]
    triggered = str(latest.late_rate_alert).lower() == "true"

    st.subheader("Delivery performance")
    st.caption(f"Latest complete delivery week: {latest.week.date()}")

    a, b, c, d = st.columns(4)
    a.metric("Delivered orders", f"{int(latest.delivered_orders):,}")
    b.metric(
        "Late delivery rate",
        f"{latest.late_rate_pct:.2f}%",
        f"{latest.change_vs_previous_4w_pp:+.2f} pp",
        delta_color="inverse",
    )
    c.metric("Average review", f"{latest.avg_review_score:.2f}/5")
    d.metric("Delivery alert", "Triggered" if triggered else "Normal")

    if triggered:
        st.warning("Late deliveries exceeded the historical threshold.")

    st.line_chart(
        alerts.tail(12).set_index("week")["late_rate_pct"],
        y_label="Late delivery rate (%)",
    )


workspace = st.sidebar.radio(
    "Workspace",
    ["Data overview", "Upload data", "Delivery investigation"],
)

if workspace == "Upload data":
    from extras.upload_view import render

    render()
    st.stop()

if workspace == "Delivery investigation":
    from investigation_view import render

    render(ROOT)
    st.stop()


st.title("Analytics | Operating Review")

if not (REPORTS / "analysis.json").exists():
    st.info("Run the analytics pipeline to generate dashboard data.")
    st.stop()

status_path = REPORTS / "last_run.json"
if status_path.exists():
    status = json.loads(status_path.read_text())
    if status.get("status") != "success":
        st.warning("The latest pipeline is incomplete. Data may be outdated.")

metrics = json.loads((REPORTS / "analysis.json").read_text())

st.caption(f"Historical e-commerce dataset | Through {metrics['cutoff']} | BRL")
st.caption(f"Weekly comparisons use data through {metrics['reporting_end']}.")

page = st.sidebar.radio("View", ["Executive", "Customers", "Operations"])
st.sidebar.caption("Reports use processed data, not a live data feed.")


if page == "Executive":
    daily = load("daily_sales")
    daily["day"] = pd.to_datetime(daily["day"])

    dates = st.slider(
        "Purchase window",
        daily.day.min().date(),
        daily.day.max().date(),
        (daily.day.min().date(), daily.day.max().date()),
    )

    filtered = daily[daily.day.between(pd.Timestamp(dates[0]), pd.Timestamp(dates[1]))]

    gmv = filtered.gmv.sum()
    orders = int(filtered.orders.sum())

    a, b, c = st.columns(3)
    a.metric("Merchandise GMV", f"BRL {gmv:,.0f}")
    b.metric("Delivered orders", f"{orders:,}")
    c.metric("Average order value", f"BRL {gmv / max(orders, 1):,.2f}")

    st.subheader("Sales trend")
    st.plotly_chart(
        px.line(filtered, x="day", y="gmv", labels={"day": "Purchase date", "gmv": "GMV (BRL)"}),
        width="stretch",
    )

    show_delivery()

    left, right = st.columns(2)

    with left:
        st.subheader("Category performance")
        growth = load("category_growth")
        growth = growth[pd.to_datetime(growth.month) <= pd.Timestamp(metrics["reporting_end"])]
        growth = growth[growth.month == growth.month.max()]
        growth = growth.sort_values("change_brl").tail(10)

        st.plotly_chart(
            px.bar(growth, x="change_brl", y="category", orientation="h"),
            width="stretch",
        )

    with right:
        st.subheader("Sales forecast")
        forecast = metrics["forecast"]
        st.dataframe(pd.DataFrame(forecast["months"]), hide_index=True)
        st.caption(forecast["warning"])
        st.write("Backtest MAE (BRL)", forecast["rolling_origin_mae_brl"])

    st.subheader("Sales anomalies")
    flags = load("anomalies")
    flags["day"] = pd.to_datetime(flags["day"])
    flags = flags[
        flags.is_anomaly & flags.day.between(pd.Timestamp(dates[0]), pd.Timestamp(dates[1]))
    ]
    st.dataframe(
        flags[["day", "gmv", "baseline", "z_score"]],
        hide_index=True,
    )


elif page == "Customers":
    a, b = st.columns(2)
    a.metric("Unique customers", f"{metrics['customers']:,}")
    b.metric("Repeat customers", f"{metrics['repeat_customer_rate']:.2%}")

    rfm = load("customer_rfm")
    segments = rfm.groupby("segment", as_index=False).agg(
        customers=("customer_unique_id", "count"),
        gmv=("monetary_value", "sum"),
    )

    st.subheader("Customer segments")
    st.plotly_chart(
        px.bar(segments, x="segment", y="gmv", color="segment"),
        width="stretch",
    )

    st.subheader("Repeat purchases after first delivery")
    st.dataframe(load("repeat_delivery_summary"), hide_index=True)
    st.caption(metrics["retention"]["interpretation"])

    st.subheader("Monthly customer retention")
    cohort = load("cohort_retention")
    matrix = cohort.pivot(
        index="cohort",
        columns="month_number",
        values="retention",
    )

    st.plotly_chart(
        px.imshow(matrix, aspect="auto", color_continuous_scale="Teal", range_color=[0, 0.05]),
        width="stretch",
    )

    st.dataframe(segments, hide_index=True)


else:
    st.subheader("Delivery performance by state")
    states = load("delivery_performance")

    minimum = st.slider("Minimum delivered orders", 1, 5000, 100)
    shown = states[states.delivered_orders >= minimum]
    shown = shown.sort_values("late_rate", ascending=False)

    st.plotly_chart(
        px.bar(shown, x="customer_state", y="late_rate", hover_data=["delivered_orders"]),
        width="stretch",
    )
    st.dataframe(shown, hide_index=True)

    st.subheader("Seller performance")
    sellers = load("seller_scorecard")
    min_orders = st.number_input("Minimum seller orders", 1, 10000, 30)

    st.dataframe(
        sellers[sellers.orders >= min_orders].sort_values("late_rate", ascending=False),
        hide_index=True,
    )

    test = metrics["delivery_test"]
    st.write(
        f"Review score difference (late vs on-time): "
        f"{test['difference_points']:.2f} points. "
        f"95% interval: {test['ci95'][0]:.2f} to {test['ci95'][1]:.2f}."
    )
    st.caption(
        "Multi-seller orders share order-level review and delivery results. "
        "These are not seller-specific ratings."
    )
    st.caption(test["interpretation"])
