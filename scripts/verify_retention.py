"""Independent raw-CSV reconstruction of all eligible customers and outcomes."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
o = pd.read_csv(
    ROOT / "data/raw/olist_orders_dataset.csv",
    parse_dates=[
        "order_purchase_timestamp",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
)
c = pd.read_csv(
    ROOT / "data/raw/olist_customers_dataset.csv", usecols=["customer_id", "customer_unique_id"]
)
o = o.merge(c, on="customer_id", validate="many_to_one").sort_values(
    ["order_purchase_timestamp", "order_id"]
)
first = o.drop_duplicates("customer_unique_id").copy()
limit = pd.Timestamp("2018-08-01")
f = first[
    (first.order_status == "delivered")
    & (first.order_purchase_timestamp >= pd.Timestamp("2017-01-01"))
    & (first.order_delivered_customer_date >= first.order_purchase_timestamp)
    & first.order_estimated_delivery_date.notna()
    & (first.order_delivered_customer_date + pd.Timedelta(days=90) < limit)
]
repeat = o[o.order_status == "delivered"][
    ["customer_unique_id", "order_id", "order_purchase_timestamp"]
].merge(
    f[["customer_unique_id", "order_delivered_customer_date", "order_id"]],
    on="customer_unique_id",
    suffixes=("_repeat", "_first"),
)
r = repeat[
    (repeat.order_id_repeat != repeat.order_id_first)
    & (repeat.order_purchase_timestamp > repeat.order_delivered_customer_date)
    & (
        repeat.order_purchase_timestamp
        <= repeat.order_delivered_customer_date + pd.Timedelta(days=90)
    )
]
counts = (
    r.groupby("customer_unique_id").size().reindex(f.customer_unique_id, fill_value=0).sort_index()
)
actual = (
    pd.read_csv(ROOT / "reports/repeat_delivery.csv")
    .set_index("customer_unique_id")
    .orders_90d.sort_index()
)
pd.testing.assert_series_equal(counts, actual, check_names=False)
print(
    f"Independent raw CSV check passed for {len(actual):,} customers and {int(actual.sum()):,} repeat orders."
)
