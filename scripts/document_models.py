"""Add column documentation without changing existing dbt tests."""

import json
from pathlib import Path

import pandas as pd
import yaml

from olist.config import engine

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTIONS = {
    "order_id": "Order identifier. Unique in the order fact; repeated on child item/payment tables.",
    "customer_id": "Order-specific customer identifier; use customer_unique_id for repeat purchases.",
    "customer_unique_id": "Stable observed buyer identifier used for cohorts and repeat purchases.",
    "gmv": "Delivered merchandise value in BRL, excluding freight. Not platform revenue.",
    "merchandise_value": "Sum of item prices per order in BRL, aggregated before joining payments and reviews.",
    "freight_value": "Sum of freight charges on order items in BRL.",
    "is_late": "Actual delivery calendar date is later than estimated delivery date; null when dates are missing.",
    "late_rate": "Late deliveries divided by deliveries with known actual and estimated dates.",
    "first_is_late": "Lateness of the first observed eligible order, using calendar dates.",
    "retention": "Distinct active customers divided by original cohort size; unobserved future months omitted.",
    "repeat_90d": "At least one subsequent delivered order purchased after first delivery and within 90 days.",
    "frequency": "Number of delivered orders per stable customer in the purchase window.",
    "monetary_value": "Total delivered merchandise value per stable customer in BRL.",
    "recency_days": "Days between analysis cutoff and most recent delivered-order purchase.",
    "order_status": "Final source-snapshot status; not status reconstructed as of the purchase date.",
    "carrier_at": "Order-level timestamp of handoff to carrier; not a separate timestamp for every seller.",
    "delivered_at": "Actual customer-delivery timestamp, nullable even for some delivered statuses.",
    "estimated_at": "Promised delivery date represented as a timestamp.",
    "purchased_at": "Timestamp when the order was purchased.",
    "approved_at": "Payment approval timestamp.",
    "seller_count": "Distinct sellers supplying an order.",
    "review_score": "Latest answered review selected deterministically per order, on a one-to-five scale.",
    "category": "Product category; missing values use the documented unknown category in business marts.",
    "delivery_denominator": "Delivered orders with non-missing actual and estimated dates.",
    "previous_gmv": "Previous calendar-month merchandise GMV, after filling observed missing months with zero.",
    "change_brl": "Current less previous month merchandise GMV in BRL.",
    "mom_pct": "Percentage change from previous month; null when previous GMV is zero.",
}


def main():
    path = ROOT / "dbt_project/models/schema.yml"
    doc = yaml.safe_load(path.read_text())
    models = {m["name"]: m for m in doc["models"]}
    manifest = json.loads((ROOT / "dbt_project/target/manifest.json").read_text())
    with engine().connect() as conn:
        fields = pd.read_sql(
            "SELECT table_schema,table_name,column_name FROM information_schema.columns WHERE table_schema IN ('staging','intermediate','marts') ORDER BY table_name,ordinal_position",
            conn,
        )
    for node in manifest["nodes"].values():
        if node["resource_type"] != "model":
            continue
        name = node["name"]
        entry = models.setdefault(name, {"name": name})
        entry["description"] = (
            node.get("description")
            or "Historical Olist "
            + name.replace("_", " ")
            + ". See docs/metric_contract.md for inclusion and date rules."
        )
        columns = {c["name"]: c for c in entry.get("columns", [])}
        for col in fields.loc[fields.table_name.eq(name), "column_name"]:
            item = columns.setdefault(col, {"name": col})
            item["description"] = DESCRIPTIONS.get(
                col,
                col.replace("_", " ").capitalize()
                + "; defined by this model SQL and its documented grain.",
            )
        entry["columns"] = list(columns.values())
    doc["models"] = list(models.values())
    path.write_text(yaml.safe_dump(doc, sort_keys=False, width=100))


if __name__ == "__main__":
    main()
