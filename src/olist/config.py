import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)
TABLE_FILES = {
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "product_category_name_translation": "product_category_name_translation.csv",
    "products": "olist_products_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
}


def engine():
    return create_engine(
        URL.create(
            "postgresql+psycopg",
            username=os.getenv("PGUSER", "olist"),
            password=os.getenv("PGPASSWORD", "olist_local"),
            host=os.getenv("PGHOST", "localhost"),
            port=int(os.getenv("PGPORT", "5433")),
            database=os.getenv("PGDATABASE", "olist"),
        ),
        pool_pre_ping=True,
    )
