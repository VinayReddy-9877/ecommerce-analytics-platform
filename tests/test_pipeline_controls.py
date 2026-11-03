import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import text

from olist import cli, quality
from olist.analysis import anomalies
from olist.config import engine
from olist.findings import risk_difference
from olist.ingest import copy_frame

ROOT = Path(__file__).parents[1]


def test_real_source_contract():
    contract = json.loads((ROOT / "data/quality_contract.json").read_text())
    result = quality.evaluate(ROOT / "data/raw", contract)
    assert result["passed"] == result["total"] == 14
    assert result["rows"] == 1550922


def test_injected_bad_timestamp_stops_before_ingestion(tmp_path, monkeypatch):
    original = quality.pd.read_csv

    def corrupt(path, **kwargs):
        frame = original(path, **kwargs)
        if Path(path).name == "olist_orders_dataset.csv":
            idx = frame.index[frame.order_status.eq("delivered")][0]
            frame.loc[idx, "order_delivered_customer_date"] = "2000-01-01 00:00:00"
        return frame

    monkeypatch.setattr(quality.pd, "read_csv", corrupt)
    contract = json.loads((ROOT / "data/quality_contract.json").read_text())
    calls = []

    def gate():
        result = quality.evaluate(ROOT / "data/raw", contract)
        (tmp_path / "quality_checks.json").write_text(json.dumps(result))
        if result["passed"] != result["total"]:
            raise ValueError("delivery before purchase")
        return result

    steps = {"quality": gate, "ingest": lambda: calls.append("ingest")}
    status = dict(
        run_id="test-failure",
        started_at=datetime.now(timezone.utc).isoformat(),
        cutoff="2018-07-31",
        status="running",
        seconds={},
    )
    with pytest.raises(ValueError, match="delivery before purchase"):
        cli.execute_steps(steps, tmp_path, status)
    assert calls == []
    assert status["status"] == "failed"
    assert status["checks_passed"] == 13
    history = pd.read_csv(tmp_path / "run_history.csv")
    assert history.status.tolist() == ["failed"]
    assert not (tmp_path / "weekly_report.md").exists()


def test_small_anomaly_baseline_is_unscored():
    days = pd.date_range("2020-01-01", periods=70)
    frame = pd.DataFrame({"day": days, "gmv": [10.0] * 69 + [10000.0]})
    result = anomalies(frame)
    assert pd.isna(result.iloc[-1].z_score)
    assert not result.iloc[-1].is_anomaly


def test_retention_gap_and_interval():
    result = risk_difference(37, 4835, 704, 61376)
    assert result["difference_pp"] == pytest.approx(-0.38177479)
    assert result["ci95_pp"] == pytest.approx([-0.64145093, -0.12209865])


@pytest.mark.skipif(
    os.getenv("OLIST_DB_TEST") != "1",
    reason="Set OLIST_DB_TEST=1 with local PostgreSQL for COPY integration",
)
def test_copy_preserves_text_nulls_and_transaction_rollback():
    name = "test_copy_" + uuid.uuid4().hex
    frame = pd.DataFrame(
        {"id": ["001", "002", "003"], "value": ['quotes " and comma, and newline\n', None, r"\N"]}
    )
    db = engine()
    with db.connect() as conn:
        transaction = conn.begin()
        try:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))
            frame.head(0).to_sql(name, conn, schema="raw", index=False)
            copy_frame(conn, name, frame)
            actual = pd.read_sql(text(f'SELECT * FROM raw."{name}" ORDER BY id'), conn)
            pd.testing.assert_frame_equal(actual, frame)
        finally:
            transaction.rollback()
        assert (
            conn.execute(text("SELECT to_regclass(:name)"), {"name": f"raw.{name}"}).scalar()
            is None
        )
