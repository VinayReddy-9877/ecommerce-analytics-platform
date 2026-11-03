from pathlib import Path

import pandas as pd

from olist import report
from olist.retention import summarize, wilson

ROOT = Path(__file__).parents[1]


def test_weekly_report_uses_last_eligible_full_week(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "analysis.json").write_text((ROOT / "reports/analysis.json").read_text())
    pd.DataFrame(
        {
            "week": ["2018-07-16", "2018-07-23", "2018-07-30", "2018-08-20"],
            "orders": [10, 12, 15, 1],
            "gmv": [100, 120, 150, 1],
            "aov": [10, 10, 10, 1],
            "is_complete_week": [True, True, True, True],
        }
    ).to_csv(reports / "weekly_kpis.csv", index=False)
    monkeypatch.setattr(report, "ROOT", tmp_path)
    report.write_report()
    text = (reports / "weekly_report.md").read_text()
    assert "Last eligible complete week: 2018-07-23" in text
    assert "+20.0%" in text


def test_wilson_interval_handles_zero_events():
    lower, upper = wilson(0, 100)
    assert abs(lower) < 1e-12 and 0 < upper < 0.05


def test_stratified_adjustment_excludes_small_groups():
    frame = pd.DataFrame(
        {
            "first_is_late": [False] * 40 + [True] * 5,
            "repeat_90d": [True] + [False] * 44,
            "repeat_30d": [False] * 45,
            "repeat_60d": [False] * 45,
            "followup_gmv_90d": [10] + [0] * 44,
            "first_purchase_month": ["2018-01"] * 45,
            "customer_state": ["SP"] * 45,
            "basket_band": ["50 to 99"] * 45,
        }
    )
    result, _ = summarize(frame)
    assert result["adjusted"]["strata"] == 0
    assert result["adjusted"]["odds_ratio"] is None


def test_retention_export_has_full_followup():
    data = pd.read_csv(ROOT / "reports/repeat_delivery.csv")
    assert data.customer_unique_id.is_unique
    assert (
        pd.to_datetime(data.first_delivered_at) + pd.Timedelta(days=90) < pd.Timestamp("2018-08-01")
    ).all()
    assert (data.orders_30d <= data.orders_60d).all()
    assert (data.orders_60d <= data.orders_90d).all()


def test_august_not_scored_as_operational_anomaly():
    data = pd.read_csv(ROOT / "reports/anomalies.csv")
    assert not data.loc[pd.to_datetime(data.day) > pd.Timestamp("2018-07-31"), "is_anomaly"].any()
