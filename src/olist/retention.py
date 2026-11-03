"""Equal-window observational comparisons, with explicit overlap restrictions."""

import numpy as np
import pandas as pd
from scipy.stats import norm
from statsmodels.stats.contingency_tables import StratifiedTable


def wilson(successes, total):
    if not total:
        return [None, None]
    z = norm.ppf(0.975)
    p = successes / total
    divisor = 1 + z * z / total
    center = (p + z * z / (2 * total)) / divisor
    margin = z * np.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / divisor
    return [float(center - margin), float(center + margin)]


def summarize(frame):
    groups = []
    for late, label in [(False, "On time"), (True, "Late")]:
        g = frame[frame.first_is_late.eq(late)]
        n = len(g)
        count = int(g.repeat_90d.sum())
        groups.append(
            dict(
                experience=label,
                customers=n,
                repeat_customers=count,
                repeat_rate=count / n if n else None,
                ci95=wilson(count, n),
                repeat_rate_30d=float(g.repeat_30d.mean()),
                repeat_rate_60d=float(g.repeat_60d.mean()),
                followup_gmv=float(g.followup_gmv_90d.sum()),
                followup_gmv_per_customer=float(g.followup_gmv_90d.mean()),
            )
        )
    tables = []
    rows = []
    for key, g in frame.groupby(["first_purchase_month", "customer_state", "basket_band"]):
        late = g[g.first_is_late]
        early = g[~g.first_is_late]
        if min(len(late), len(early)) < 20:
            continue
        a = int(late.repeat_90d.sum())
        b = len(late) - a
        c = int(early.repeat_90d.sum())
        d = len(early) - c
        if a + c == 0 or b + d == 0:
            continue
        tables.append(np.array([[a, b], [c, d]]))
        rows.append(
            dict(
                month=str(key[0]),
                state=key[1],
                basket_band=key[2],
                late_n=len(late),
                on_time_n=len(early),
                late_repeat=a,
                on_time_repeat=c,
            )
        )
    adjusted = {
        "method": "Mantel-Haenszel odds ratio, stratified by first-purchase month, state and basket band; >=20 customers per exposure group and outcome variation per stratum.",
        "strata": len(tables),
        "overlap_customers": sum(x["late_n"] + x["on_time_n"] for x in rows),
    }
    if tables:
        model = StratifiedTable(np.stack(tables, axis=2))
        adjusted.update(
            odds_ratio=float(model.oddsratio_pooled),
            ci95=[float(x) for x in model.oddsratio_pooled_confint()],
        )
    else:
        adjusted.update(odds_ratio=None, ci95=[None, None])
    return {
        "groups": groups,
        "adjusted": adjusted,
        "eligible_customers": len(frame),
        "risk_difference_pp": 100 * (groups[1]["repeat_rate"] - groups[0]["repeat_rate"]),
        "interpretation": "Association, not causal lift. Equal 90-day follow-up begins at first delivery. Excludes earlier repeat purchases and customers whose first observed order was not delivered. Adjustment covers only observed strata and may not generalize outside overlap.",
    }, pd.DataFrame(rows)
