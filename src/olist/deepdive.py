"""Reproducible operational diagnostics from raw Olist files and validated exports.

Handoff timing is a proxy, not an allocation of fault. Multi-seller orders are
excluded from seller handling and distance analysis because the carrier timestamp
is recorded at order level. All joins below declare their expected cardinality.
"""

import json

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from .config import ROOT, TABLE_FILES


def haversine(lat1, lon1, lat2, lon2):
    a, b, c, d = [np.radians(v) for v in (lat1, lon1, lat2, lon2)]
    h = np.sin((c - a) / 2) ** 2 + np.cos(a) * np.cos(c) * np.sin((d - b) / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))


def run():
    out = ROOT / "reports"
    metrics = json.loads((out / "analysis.json").read_text())
    cutoff = pd.Timestamp(metrics["cutoff"]) + pd.Timedelta(days=1)

    def raw(name):
        return pd.read_csv(
            ROOT / "data/raw" / TABLE_FILES[name],
            dtype={
                "customer_zip_code_prefix": str,
                "seller_zip_code_prefix": str,
                "geolocation_zip_code_prefix": str,
            },
            low_memory=False,
        )

    def save(name, frame):
        frame.to_csv(out / f"{name}.csv", index=False)

    orders, items, customers, sellers = [
        raw(n) for n in ("orders", "order_items", "customers", "sellers")
    ]
    for col in orders.columns:
        if col.endswith(("_timestamp", "_date")) or col == "order_approved_at":
            orders[col] = pd.to_datetime(orders[col], errors="coerce")
    items["shipping_limit_date"] = pd.to_datetime(items.shipping_limit_date)
    summary = items.groupby("order_id").agg(
        seller_count=("seller_id", "nunique"),
        seller_id=("seller_id", "first"),
        earliest_deadline=("shipping_limit_date", "min"),
        latest_deadline=("shipping_limit_date", "max"),
        gmv=("price", "sum"),
    )
    data = (
        orders.loc[
            (orders.order_status == "delivered") & (orders.order_purchase_timestamp < cutoff)
        ]
        .merge(summary, on="order_id", validate="one_to_one")
        .merge(customers, on="customer_id", validate="many_to_one")
    )
    known = data.order_delivered_customer_date.notna() & data.order_estimated_delivery_date.notna()
    data["late"] = (
        (
            data.order_delivered_customer_date.dt.normalize()
            > data.order_estimated_delivery_date.dt.normalize()
        )
        .astype(float)
        .where(known)
    )
    data["handling_days"] = (
        data.order_delivered_carrier_date - data.order_approved_at
    ).dt.total_seconds() / 86400
    data["transit_days"] = (
        data.order_delivered_customer_date - data.order_delivered_carrier_date
    ).dt.total_seconds() / 86400
    data["promise_days"] = (
        data.order_estimated_delivery_date - data.order_purchase_timestamp
    ).dt.total_seconds() / 86400
    data["promise_slack_days"] = (
        data.order_estimated_delivery_date - data.order_delivered_customer_date
    ).dt.total_seconds() / 86400
    data["handoff_eligible"] = (
        data.seller_count.eq(1)
        & data.handling_days.ge(0)
        & data.transit_days.ge(0)
        & data.earliest_deadline.notna()
    )
    data["late_handoff"] = (
        (data.order_delivered_carrier_date > data.earliest_deadline)
        .astype(float)
        .where(data.handoff_eligible)
    )
    data["late_handoff_latest_deadline"] = (
        (data.order_delivered_carrier_date > data.latest_deadline)
        .astype(float)
        .where(data.handoff_eligible)
    )
    geo = raw("geolocation")
    geo = geo[geo.geolocation_lat.between(-34, 6) & geo.geolocation_lng.between(-74, -34)]
    geo = geo.groupby("geolocation_zip_code_prefix")[
        ["geolocation_lat", "geolocation_lng"]
    ].median()
    data = data.merge(
        sellers[["seller_id", "seller_zip_code_prefix"]], on="seller_id", validate="many_to_one"
    )
    for side in ("customer", "seller"):
        data[f"{side}_lat"] = data[f"{side}_zip_code_prefix"].map(geo.geolocation_lat)
        data[f"{side}_lon"] = data[f"{side}_zip_code_prefix"].map(geo.geolocation_lng)
    data["distance_km"] = haversine(
        data.customer_lat, data.customer_lon, data.seller_lat, data.seller_lon
    ).where(data.seller_count.eq(1))
    save("delivery_diagnostics", data)
    eligible = data[data.handoff_eligible & data.late.notna()]
    late = eligible[eligible.late.eq(1)]
    state = (
        data.groupby("customer_state")
        .agg(
            delivered_orders=("order_id", "size"),
            known_deliveries=("late", "count"),
            late_orders=("late", "sum"),
            late_rate=("late", "mean"),
            median_distance_km=("distance_km", "median"),
            median_transit_days=("transit_days", "median"),
            median_promise_days=("promise_days", "median"),
            median_slack_days=("promise_slack_days", "median"),
        )
        .reset_index()
    )
    save("state_diagnostics", state)
    handoff = (
        eligible.groupby(["customer_state", "late_handoff"])
        .agg(orders=("order_id", "size"), late_orders=("late", "sum"), late_rate=("late", "mean"))
        .reset_index()
    )
    save("handoff_by_state", handoff)
    modeldata = eligible.dropna(subset=["distance_km"]).copy()
    modeldata["log_distance"] = np.log1p(modeldata.distance_km)
    modeldata["purchase_month"] = modeldata.order_purchase_timestamp.dt.strftime("%Y-%m")
    modelrows, models = [], {}
    for outcome in ("transit_days", "late"):
        for kind, formula in [
            ("distance_only", f"{outcome} ~ log_distance"),
            ("state_month", f"{outcome} ~ log_distance + C(customer_state) + C(purchase_month)"),
        ]:
            fit = smf.ols(formula, modeldata).fit(cov_type="HC3")
            models[f"{outcome}_{kind}_r2"] = float(fit.rsquared)
            for name, value in fit.params.items():
                modelrows.append(
                    {
                        "outcome": outcome,
                        "model": kind,
                        "term": name,
                        "coefficient": value,
                        "ci_low": fit.conf_int().loc[name, 0],
                        "ci_high": fit.conf_int().loc[name, 1],
                    }
                )
            if kind == "state_month":
                models[f"{outcome}_adjusted_RJ_minus_SP"] = float(
                    fit.params.get("C(customer_state)[T.RJ]", 0)
                    - fit.params.get("C(customer_state)[T.SP]", 0)
                )
    models["orders"] = len(modeldata)
    models["transit_distance_spearman"] = float(
        modeldata.transit_days.corr(modeldata.distance_km, method="spearman")
    )
    save("distance_model_coefficients", pd.DataFrame(modelrows))
    modeldata["distance_band"] = pd.cut(
        modeldata.distance_km, [0, 100, 300, 700, 1500, np.inf], include_lowest=True
    ).astype(str)
    save(
        "distance_bands",
        modeldata.groupby("distance_band")
        .agg(
            orders=("order_id", "size"),
            late_rate=("late", "mean"),
            median_transit_days=("transit_days", "median"),
        )
        .reset_index(),
    )
    delivered_items = items.merge(
        data[["order_id", "order_purchase_timestamp", "customer_state", "late"]],
        on="order_id",
        validate="many_to_one",
    )
    concentration = (
        delivered_items.groupby("seller_id")
        .price.sum()
        .sort_values(ascending=False)
        .reset_index(name="gmv")
    )
    concentration["rank"] = np.arange(1, len(concentration) + 1)
    concentration["running_share"] = concentration.gmv.cumsum() / concentration.gmv.sum()
    save("seller_concentration", concentration)
    payments = (
        raw("order_payments")
        .groupby("order_id")
        .agg(
            max_installments=("payment_installments", "max"), payment_total=("payment_value", "sum")
        )
    )
    payments = data[["order_id", "gmv"]].merge(payments, on="order_id", validate="one_to_one")
    save(
        "installment_behavior",
        payments.groupby("max_installments")
        .agg(
            orders=("order_id", "size"),
            merchandise_aov=("gmv", "mean"),
            mean_payment=("payment_total", "mean"),
        )
        .reset_index(),
    )
    # Sensitivity uses the existing eligible first-order cohort, never a changed denominator.
    cohort = pd.read_csv(out / "repeat_delivery.csv")
    for col in ("first_purchase_at", "first_delivered_at"):
        cohort[col] = pd.to_datetime(cohort[col])
    candidates = cohort[
        ["customer_unique_id", "first_order_id", "first_purchase_at", "first_delivered_at"]
    ].merge(
        data[["customer_unique_id", "order_id", "order_purchase_timestamp"]],
        on="customer_unique_id",
        validate="one_to_many",
    )
    candidates = candidates[
        (candidates.order_id != candidates.first_order_id)
        & (candidates.order_purchase_timestamp > candidates.first_purchase_at)
        & (
            candidates.order_purchase_timestamp
            <= candidates.first_delivered_at + pd.Timedelta(days=90)
        )
    ]
    anyrepeat = set(candidates.customer_unique_id)
    cohort["any_repeat"] = cohort.customer_unique_id.isin(anyrepeat)
    sensitivity = []
    for mode, column in [
        ("After first delivery", "repeat_90d"),
        ("After first purchase through delivery + 90 days", "any_repeat"),
    ]:
        for islate, group in cohort.groupby("first_is_late"):
            sensitivity.append(
                {
                    "definition": mode,
                    "experience": "Late" if islate else "On time",
                    "customers": len(group),
                    "repeat_customers": int(group[column].sum()),
                    "repeat_rate": float(group[column].mean()),
                }
            )
    save("retention_sensitivity", pd.DataFrame(sensitivity))
    bystate = state.set_index("customer_state")
    rj, sp = bystate.loc["RJ"], bystate.loc["SP"]
    avoided = float(rj.late_orders - rj.known_deliveries * sp.late_rate)
    result = {
        "delivered_orders": len(data),
        "handoff_eligible_orders": len(eligible),
        "eligible_late_orders": len(late),
        "late_orders_with_timely_handoff": int(late.late_handoff.eq(0).sum()),
        "late_orders_with_late_handoff": int(late.late_handoff.eq(1).sum()),
        "models": models,
        "seller_count": len(concentration),
        "sellers_for_80pct_gmv": int(
            concentration.loc[concentration.running_share.ge(0.8), "rank"].iloc[0]
        ),
        "top_10_seller_share": float(concentration.head(10).gmv.sum() / concentration.gmv.sum()),
        "rj_scenario": {
            "known_orders": int(rj.known_deliveries),
            "late_orders": int(rj.late_orders),
            "rj_late_rate": float(rj.late_rate),
            "sp_late_rate": float(sp.late_rate),
            "fewer_late_orders": avoided,
            "average_review_change_scenario_range": [
                0,
                float(
                    (rj.late_rate - sp.late_rate)
                    * (
                        metrics["delivery_test"]["on_time_mean"]
                        - metrics["delivery_test"]["late_mean"]
                    )
                ),
            ],
        },
        "caveats": [
            "Handoff timestamp is order-level and may not identify seller or carrier fault.",
            "Geolocation uses median coordinates per ZIP prefix; distance is straight-line, not a route.",
            "Models are descriptive in-sample associations; R squared is not a causal attribution.",
            "RJ scenario assumes SP rate is attainable. Review range assumes zero to full transfer of the observed association; it is not a confidence interval or forecast.",
            "Retention sensitivity includes a longer exposure window when counting pre-delivery purchases.",
        ],
    }
    (out / "deepdive.json").write_text(json.dumps(result, indent=2))
    # Separate facts prevent multiplication of order counts through item joins.
    fact = data[
        [
            "order_id",
            "order_purchase_timestamp",
            "customer_unique_id",
            "customer_state",
            "gmv",
            "late",
        ]
    ].rename(columns={"order_purchase_timestamp": "day"})
    fact["day"] = fact.day.dt.normalize()
    save("bi_orders", fact)
    products = raw("products")[["product_id", "product_category_name"]]
    translation = raw("product_category_name_translation")
    products = products.merge(
        translation, on="product_category_name", how="left", validate="many_to_one"
    )
    delivered_items = delivered_items.merge(
        products, on="product_id", how="left", validate="many_to_one"
    )
    delivered_items["category"] = delivered_items.product_category_name_english.fillna(
        delivered_items.product_category_name
    ).fillna("Unknown")
    delivered_items["day"] = delivered_items.order_purchase_timestamp.dt.normalize()
    save(
        "bi_items",
        delivered_items[
            [
                "order_id",
                "order_item_id",
                "day",
                "seller_id",
                "category",
                "customer_state",
                "price",
                "late",
            ]
        ],
    )
    save("dim_seller", sellers[["seller_id", "seller_state"]])
    save("dim_state", pd.DataFrame({"customer_state": sorted(data.customer_state.unique())}))
    save("dim_category", pd.DataFrame({"category": sorted(delivered_items.category.unique())}))
    calendar = pd.DataFrame(
        {"day": pd.date_range(f"{fact.day.min().year}-01-01", f"{fact.day.max().year}-12-31")}
    )
    calendar["year"] = calendar.day.dt.year
    calendar["month"] = calendar.day.dt.month
    calendar["year_month"] = calendar.day.dt.strftime("%Y-%m")
    save("dim_calendar", calendar)
    from .findings import run as summarize_findings

    summarize_findings()
    return result
