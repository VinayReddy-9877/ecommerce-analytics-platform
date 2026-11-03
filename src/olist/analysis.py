"""Generate business analysis from the PostgreSQL warehouse."""

import json

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from .config import ROOT, engine
from .retention import summarize


def anomalies(daily, window=56, threshold=3.0, min_baseline_brl=1000.0):
    result = daily.sort_values("day").copy()
    result["weekday"] = pd.to_datetime(result.day).dt.day_of_week

    grouped = result.groupby("weekday")["gmv"]
    result["baseline"] = grouped.transform(
        lambda s: s.shift().rolling(window // 7, min_periods=6).mean()
    )
    result["baseline_std"] = grouped.transform(
        lambda s: s.shift().rolling(window // 7, min_periods=6).std()
    )

    result["z_score"] = (result.gmv - result.baseline) / result.baseline_std.replace(0, np.nan)
    result["baseline_eligible"] = result.baseline.ge(min_baseline_brl)
    result.loc[~result.baseline_eligible, "z_score"] = np.nan
    result["is_anomaly"] = result.z_score.abs() > threshold

    return result


def delivery_test(orders):
    late = orders.loc[orders.is_late.eq(True), "review_score"].dropna().astype(float)
    on_time = orders.loc[orders.is_late.eq(False), "review_score"].dropna().astype(float)

    if min(len(late), len(on_time)) < 2:
        raise ValueError("Not enough reviewed orders in both delivery groups")

    result = stats.ttest_ind(late, on_time, equal_var=False)

    late_var = late.var() / len(late)
    on_time_var = on_time.var() / len(on_time)
    variance = late_var + on_time_var

    df = variance**2 / (late_var**2 / (len(late) - 1) + on_time_var**2 / (len(on_time) - 1))

    difference = late.mean() - on_time.mean()
    margin = stats.t.ppf(0.975, df) * np.sqrt(variance)

    return {
        "late_n": len(late),
        "on_time_n": len(on_time),
        "late_mean": late.mean(),
        "on_time_mean": on_time.mean(),
        "difference_points": difference,
        "ci95": [difference - margin, difference + margin],
        "welch_p_value": float(result.pvalue),
        "interpretation": (
            "Observational association; reviews are ordinal and confounding is not controlled."
        ),
    }


def forecast(monthly):
    series = monthly.set_index("month").gmv.astype(float).sort_index()
    series.index = pd.DatetimeIndex(series.index)
    series = series.loc["2017-01-01":].asfreq("MS")

    if len(series) < 12 or series.isna().any():
        raise ValueError("Need at least 12 consecutive complete months")

    def predict(train, kind):
        if kind == "last_month":
            return np.repeat(train.iloc[-1], 3)

        model = ExponentialSmoothing(
            train,
            trend="add",
            damped_trend=True,
            initialization_method="estimated",
        )
        return np.maximum(0, model.fit(optimized=True).forecast(3).values)

    scores = {}
    errors = {}

    for kind in ["last_month", "damped_trend"]:
        residuals = []

        for split in range(max(8, len(series) - 6), len(series) - 2):
            actual = series.iloc[split : split + 3].values
            predicted = predict(series.iloc[:split], kind)
            residuals.extend(actual - predicted)

        scores[kind] = float(np.mean(np.abs(residuals)))
        errors[kind] = residuals

    chosen = min(scores, key=scores.get)
    values = predict(series, chosen)
    radius = float(np.quantile(np.abs(errors[chosen]), 0.9))

    months = pd.date_range(
        series.index[-1] + pd.offsets.MonthBegin(1),
        periods=3,
        freq="MS",
    )

    return {
        "model": chosen,
        "rolling_origin_mae_brl": scores,
        "history_months": len(series),
        "warning": (
            "Historical extrapolation with few backtests. "
            "Bands are empirical error ranges, not calibrated confidence intervals."
        ),
        "months": [
            {
                "month": str(day.date()),
                "gmv": float(value),
                "lower": max(0, float(value - radius)),
                "upper": float(value + radius),
            }
            for day, value in zip(months, values)
        ],
    }


def analyze(reporting_end="2018-07-31"):
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)

    tables = [
        "daily_sales",
        "monthly_sales",
        "customer_rfm",
        "repeat_delivery",
        "cohort_retention",
        "delivery_performance",
        "seller_scorecard",
        "category_growth",
        "weekly_kpis",
        "weekly_delivery_kpis",
        "weekly_delivery_alerts",
    ]

    with engine().connect() as conn:
        audit_sql = (ROOT / "sql/data_quality_audit.sql").read_text()
        audit = pd.read_sql(audit_sql, conn)
        audit.to_csv(out / "data_quality_audit.csv", index=False)

        orders = pd.read_sql(
            "select * from marts.fct_orders where order_status='delivered'",
            conn,
        )

        data = {}

        for table in tables:
            query = f"select * from marts.{table}"

            if table == "daily_sales":
                query += " order by day"
            elif table == "monthly_sales":
                query += " order by month"
            elif table == "customer_rfm":
                query += " order by monetary_value desc"

            data[table] = pd.read_sql(query, conn)
            data[table].to_csv(out / f"{table}.csv", index=False)

    daily = data["daily_sales"]
    monthly = data["monthly_sales"]
    rfm = data["customer_rfm"]
    repeat = data["repeat_delivery"]

    cutoff = pd.Timestamp(daily.day.max())
    reporting_end = min(cutoff, pd.Timestamp(reporting_end))

    # Exclude the partial final month from forecasting.
    monthly = monthly[pd.to_datetime(monthly.month) + pd.offsets.MonthEnd(0) <= reporting_end]

    retention, strata = summarize(repeat)

    strata.to_csv(out / "repeat_delivery_strata.csv", index=False)

    pd.DataFrame(retention["groups"]).drop(columns="ci95").to_csv(
        out / "repeat_delivery_summary.csv",
        index=False,
    )

    (out / "retention_analysis.json").write_text(json.dumps(retention, indent=2, allow_nan=False))

    adjustment = {
        key: value for key, value in retention["adjusted"].items() if key not in ["ci95", "method"]
    }
    pd.DataFrame([adjustment]).to_csv(
        out / "retention_adjustment.csv",
        index=False,
    )

    anomaly = anomalies(daily)
    anomaly["eligible_for_reporting"] = pd.to_datetime(anomaly.day) <= reporting_end
    anomaly["is_anomaly"] = anomaly.is_anomaly & anomaly.eligible_for_reporting
    anomaly.to_csv(out / "anomalies.csv", index=False)

    threshold = rfm.monetary_value.sum() * 0.8
    top_n = int(np.searchsorted(rfm.monetary_value.cumsum(), threshold) + 1)

    metrics = {
        "cutoff": str(cutoff.date()),
        "reporting_end": str(reporting_end.date()),
        "reporting_policy": (
            "Preserve August in descriptive totals; exclude August from "
            "comparisons and forecasting due to end-of-snapshot coverage uncertainty."
        ),
        "retention": retention,
        "delivered_orders": len(orders),
        "gmv_brl": float(orders.merchandise_value.sum()),
        "aov_brl": float(orders.merchandise_value.mean()),
        "customers": len(rfm),
        "repeat_customer_rate": float((rfm.frequency > 1).mean()),
        "customers_for_80pct_gmv": top_n,
        "customer_share_for_80pct_gmv": top_n / len(rfm),
        "late_rate": float(orders.is_late.dropna().mean()),
        "anomaly_days": int(anomaly.is_anomaly.sum()),
        "delivery_test": delivery_test(orders),
        "forecast": forecast(monthly),
    }

    (out / "analysis.json").write_text(json.dumps(metrics, indent=2, allow_nan=False))

    return metrics
