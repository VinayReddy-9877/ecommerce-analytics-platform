import json
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from olist.deepdive import haversine
from olist.extras.uploads import analyze_mapped, read_upload
from olist.report import validate_numeric_draft

ROOT = Path(__file__).parents[1]


def test_upload_ids_and_headers():
    frame = read_upload("test.csv", b"order_id,value\n001,2\n002,\n")
    assert frame.order_id.iloc[0] == "001"
    assert pd.isna(frame.value.iloc[1])
    with pytest.raises(ValueError, match="unique"):
        read_upload("bad.csv", b"a,a\n1,2")


def test_mapped_delivery_uses_calendar_dates_and_excludes_unknown():
    frame = pd.DataFrame(
        {
            "id": ["a", "b", "c"],
            "date": ["2024-01-01"] * 3,
            "amount": ["10", "20", "30"],
            "customer": ["x", "x", "y"],
            "actual": ["2024-01-03T14:00:00", "2024-01-05", None],
            "promise": ["2024-01-03"] * 3,
        }
    )
    metrics, tables = analyze_mapped(
        frame,
        {
            "order_id": "id",
            "date": "date",
            "amount": "amount",
            "customer_id": "customer",
            "delivered": "actual",
            "estimated": "promise",
            "grain": "order",
            "currency": "BRL",
        },
    )
    assert metrics["late_rate"] == 0.5
    assert metrics["delivery_excluded_orders"] == 1
    assert metrics["repeat_customer_rate"] == 0.5
    assert tables["customers"].frequency.sum() == 3


def test_cohort_missing_observed_month_is_zero():
    frame = pd.DataFrame(
        {
            "id": ["a", "b"],
            "date": ["2024-01-01", "2024-03-02"],
            "amount": ["10", "20"],
            "customer": ["x", "x"],
        }
    )
    _, tables = analyze_mapped(
        frame,
        dict(
            order_id="id",
            date="date",
            amount="amount",
            customer_id="customer",
            grain="order",
            currency="BRL",
        ),
    )
    assert tables["cohorts"].retention.tolist() == [1, 0, 1]


def test_upload_and_investigation_render():
    app = AppTest.from_file(str(ROOT / "dashboards/app.py"), default_timeout=30).run()
    for page in ["Upload data", "Delivery investigation"]:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception


def test_numeric_guard():
    assert validate_numeric_draft("GMV {{gmv}}", {"gmv": "BRL 50"}) == "GMV BRL 50"
    for bad in ["GMV 50", "GMV fifty 50", "ten percent", "{{invented}}"]:
        with pytest.raises(ValueError):
            validate_numeric_draft(bad, {})


def test_haversine_known_distance():
    assert haversine(0, 0, 0, 1) == pytest.approx(111.195, abs=0.001)
    assert haversine(0, 0, 0, 0) == 0


def test_deepdive_reconciles_and_sensitivity_denominators():
    d = json.loads((ROOT / "reports/deepdive.json").read_text())
    facts = pd.read_csv(ROOT / "reports/bi_orders.csv")
    items = pd.read_csv(ROOT / "reports/bi_items.csv")
    assert facts.order_id.is_unique
    assert facts.gmv.sum() == pytest.approx(items.price.sum())
    assert (
        d["late_orders_with_timely_handoff"] + d["late_orders_with_late_handoff"]
        == d["eligible_late_orders"]
    )
    sensitivity = pd.read_csv(ROOT / "reports/retention_sensitivity.csv")
    assert sensitivity.groupby("definition").customers.sum().nunique() == 1
    for _, g in sensitivity.groupby("experience"):
        assert g.iloc[1].repeat_customers >= g.iloc[0].repeat_customers


def test_sql_and_python_handoff_counts_agree():
    sql = pd.read_csv(ROOT / "sql/showcase/samples/10_handoff_transit.csv")
    calculated = json.loads((ROOT / "reports/deepdive.json").read_text())
    assert (
        int(sql.loc[~sql.late_handoff, "late_orders"].sum())
        == calculated["late_orders_with_timely_handoff"]
    )
    assert (
        int(sql.loc[sql.late_handoff, "late_orders"].sum())
        == calculated["late_orders_with_late_handoff"]
    )
