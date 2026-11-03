"""Transactional snapshot replacement with COPY on the SQLAlchemy-owned connection."""

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from psycopg import sql
from sqlalchemy import text

from .config import ROOT, TABLE_FILES, engine

log = logging.getLogger(__name__)


def copy_frame(conn, table, frame):
    statement = sql.SQL("COPY {}.{} ({}) FROM STDIN").format(
        sql.Identifier("raw"),
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(c) for c in frame.columns),
    )
    with conn.connection.driver_connection.cursor() as cursor:
        with cursor.copy(statement) as copy:
            for row in frame.where(frame.notna(), None).itertuples(index=False, name=None):
                copy.write_row(tuple(None if pd.isna(value) else value for value in row))


def ingest(raw_dir=None, method="copy"):
    if method not in {"copy", "insert"}:
        raise ValueError("method must be copy or insert")
    raw_dir = Path(raw_dir) if raw_dir else ROOT / "data/raw"
    started = time.perf_counter()
    records = []
    with engine().begin() as conn:
        conn.execute(text("select pg_advisory_xact_lock(782341)"))
        conn.execute(text("create schema if not exists raw"))
        for table, filename in sorted(TABLE_FILES.items()):
            path = raw_dir / filename
            frame = pd.read_csv(path, dtype=str)
            if frame.empty:
                raise ValueError(f"Empty source: {filename}")
            exists = conn.execute(
                text("select to_regclass(:name)"), {"name": f"raw.{table}"}
            ).scalar()
            if exists:
                conn.execute(text(f'DELETE FROM raw."{table}"'))
            if method == "insert":
                frame.to_sql(
                    table, conn, schema="raw", if_exists="append", index=False, chunksize=5000
                )
            else:
                if not exists:
                    frame.head(0).to_sql(table, conn, schema="raw", index=False)
                copy_frame(conn, table, frame)
            records.append(
                dict(
                    table=table,
                    rows=len(frame),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    null_cells=int(frame.isna().sum().sum()),
                    duplicate_rows=int(frame.duplicated().sum()),
                )
            )
            log.info("Loaded %s: %s rows", table, len(frame))
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    result = dict(
        loaded_at=datetime.now(timezone.utc).isoformat(),
        method=method,
        seconds=round(time.perf_counter() - started, 3),
        tables=records,
    )
    (out / "ingestion.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
