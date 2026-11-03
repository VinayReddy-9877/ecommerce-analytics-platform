"""Snapshot contract checked before ingestion; failed inputs never reach PostgreSQL."""

import json
from pathlib import Path

import pandas as pd

from .config import ROOT, TABLE_FILES


def evaluate(raw_dir, contract):
    frames, checks = {}, []

    def check(name, observed, limit, passed):
        checks.append(dict(name=name, observed=observed, limit=limit, passed=bool(passed)))

    for table, filename in sorted(TABLE_FILES.items()):
        frames[table] = pd.read_csv(Path(raw_dir) / filename, dtype=str)
        count = len(frames[table])
        expected = contract["rows"][filename]
        tolerance = contract["row_count_relative_tolerance"]
        check(
            f"{table}: row count",
            count,
            f"{expected} +/- {tolerance:.0%}",
            abs(count - expected) <= expected * tolerance,
        )
    orders = frames["orders"]
    delivered = orders[orders.order_status.eq("delivered")]
    actual = pd.to_datetime(delivered.order_delivered_customer_date, errors="coerce")
    purchased = pd.to_datetime(delivered.order_purchase_timestamp, errors="coerce")
    check(
        "delivered timestamp null rate",
        float(actual.isna().mean()),
        contract["max_delivered_timestamp_null_rate"],
        actual.isna().mean() <= contract["max_delivered_timestamp_null_rate"],
    )
    reviewed = set(
        frames["order_reviews"].loc[frames["order_reviews"].review_score.notna(), "order_id"]
    )
    missing_reviews = float((~delivered.order_id.isin(reviewed)).mean())
    check(
        "delivered review null rate",
        missing_reviews,
        contract["max_delivered_review_null_rate"],
        missing_reviews <= contract["max_delivered_review_null_rate"],
    )
    reversed_dates = int((actual < purchased).sum())
    check("delivery before purchase", reversed_dates, 0, reversed_dates == 0)
    seller_orders = set(
        frames["order_items"].loc[frames["order_items"].seller_id.notna(), "order_id"]
    )
    no_seller = int((~delivered.order_id.isin(seller_orders)).sum())
    check("delivered orders without seller", no_seller, 0, no_seller == 0)
    bad_ids = int(orders.order_id.isna().sum() + orders.order_id.duplicated().sum())
    check("missing or duplicate order IDs", bad_ids, 0, bad_ids == 0)
    return {
        "rows": sum(len(f) for f in frames.values()),
        "checks": checks,
        "passed": sum(c["passed"] for c in checks),
        "total": len(checks),
    }


def run(raw_dir=None):
    raw_dir = Path(raw_dir) if raw_dir else ROOT / "data/raw"
    contract = json.loads((ROOT / "data/quality_contract.json").read_text())
    result = evaluate(raw_dir, contract)
    output = ROOT / "reports/quality_checks.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    failures = [c["name"] for c in result["checks"] if not c["passed"]]
    if failures:
        raise ValueError("Source quality gate failed: " + ", ".join(failures))
    return result
