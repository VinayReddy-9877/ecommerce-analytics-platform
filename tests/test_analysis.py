import numpy as np
import pandas as pd
import pytest

from olist.analysis import anomalies, delivery_test, forecast


def test_anomaly_baseline_does_not_include_current_or_future():
    daily = pd.DataFrame(
        {
            "day": pd.date_range("2020-01-01", periods=100),
            "gmv": np.tile([90.0, 100.0, 110.0, 120.0, 100.0], 20),
        }
    )
    baseline = anomalies(daily, min_baseline_brl=0)
    changed = daily.copy()
    changed.loc[80:, "gmv"] = 1000000
    actual = anomalies(changed, min_baseline_brl=0)
    pd.testing.assert_series_equal(actual.baseline.iloc[:81], baseline.baseline.iloc[:81])
    assert actual.is_anomaly.iloc[80]


def test_constant_history_does_not_produce_infinite_scores():
    daily = pd.DataFrame({"day": pd.date_range("2020-01-01", periods=100), "gmv": 1.0})
    assert anomalies(daily).z_score.isna().all()


def test_delivery_direction_and_missing_reviews():
    data = pd.DataFrame(
        {
            "is_late": [True] * 4 + [False] * 4,
            "review_score": [1, 2, 2, None, 4, 5, 5, 4],
        }
    )
    result = delivery_test(data)
    assert result["late_n"] == 3
    assert result["difference_points"] < 0
    assert result["ci95"][1] < 0


def test_forecast_rejects_short_history():
    data = pd.DataFrame({"month": pd.date_range("2020-01-01", periods=8, freq="MS"), "gmv": 100.0})
    with pytest.raises(ValueError):
        forecast(data)
