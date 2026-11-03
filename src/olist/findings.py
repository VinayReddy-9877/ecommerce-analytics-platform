"""Rate denominators, interval estimates and explicitly descriptive scenarios."""

import json

import numpy as np
import pandas as pd
from scipy.stats import norm

from .config import ROOT


def risk_difference(late_count, late_n, ontime_count, ontime_n):
    """Unpooled normal interval for two independent binomial proportions, in pp."""
    if min(late_n, ontime_n) == 0:
        return dict(difference_pp=None, ci95_pp=[None, None])
    p, q = late_count / late_n, ontime_count / ontime_n
    margin = norm.ppf(0.975) * np.sqrt(p * (1 - p) / late_n + q * (1 - q) / ontime_n)
    return dict(
        difference_pp=100 * (p - q), ci95_pp=[100 * (p - q - margin), 100 * (p - q + margin)]
    )


def summarize(reports):
    data = pd.read_csv(reports / "delivery_diagnostics.csv")
    eligible = data[data.handoff_eligible & data.late.notna()]
    handoff = (
        eligible.groupby("late_handoff")
        .agg(orders=("order_id", "size"), late_orders=("late", "sum"))
        .reset_index()
    )
    handoff["late_rate"] = handoff.late_orders / handoff.orders
    handoff["order_share"] = handoff.orders / handoff.orders.sum()
    handoff["late_order_share"] = handoff.late_orders / handoff.late_orders.sum()
    handoff["handoff"] = handoff.late_handoff.map({0: "Timely", 1: "Late"})
    handoff.to_csv(reports / "handoff_rates.csv", index=False)
    h = handoff.set_index("late_handoff")
    benchmark = float(h.loc[1, "late_orders"] - h.loc[1, "orders"] * h.loc[0, "late_rate"])
    retention = pd.read_csv(reports / "retention_sensitivity.csv")
    differences = []
    for definition, frame in retention.groupby("definition", sort=False):
        f = frame.set_index("experience")
        a, b = f.loc["Late"], f.loc["On time"]
        differences.append(
            dict(
                definition=definition,
                late_n=int(a.customers),
                late_repeat=int(a.repeat_customers),
                on_time_n=int(b.customers),
                on_time_repeat=int(b.repeat_customers),
                **risk_difference(a.repeat_customers, a.customers, b.repeat_customers, b.customers),
            )
        )
    # Standardize the other states to RJ's distance-band distribution; exclude RJ from reference.
    geo = eligible.dropna(subset=["distance_km"]).copy()
    geo["band"] = pd.cut(
        geo.distance_km, [0, 100, 300, 700, 1500, np.inf], include_lowest=True
    ).astype(str)
    reference = geo[geo.customer_state.ne("RJ")].groupby("band").late.agg(["mean", "size"])
    rj = geo[geo.customer_state.eq("RJ")].groupby("band").late.agg(["sum", "size"])
    bands = rj.join(reference, lsuffix="_rj", rsuffix="_other").dropna()
    bands["expected"] = bands.size_rj * bands["mean"]
    bands.to_csv(reports / "rj_distance_benchmark.csv", index_label="distance_band")
    result = {
        "handoff": handoff.to_dict("records"),
        "handoff_rate_ratio": float(h.loc[1, "late_rate"] / h.loc[0, "late_rate"]),
        "handoff_scenario_fewer": benchmark,
        "retention_differences": differences,
        "rj_distance_scenario": {
            "eligible_rj_orders": int(bands.size_rj.sum()),
            "observed_late": int(bands["sum"].sum()),
            "expected_late": float(bands.expected.sum()),
            "fewer_late": float(bands["sum"].sum() - bands.expected.sum()),
            "reference": "Non-RJ eligible single-seller orders, standardized to RJ distance bands",
        },
        "limitations": [
            "Scenarios are comparisons, not avoidable orders or causal effects.",
            "SP comparison is not a statistical upper bound.",
            "Distance-only R squared is in-sample fit, not a causal fraction.",
            "Retention intervals use an unpooled normal approximation; only 37 late-customer repeat events in the full snapshot.",
        ],
    }
    (reports / "findings.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def run():
    return summarize(ROOT / "reports")
