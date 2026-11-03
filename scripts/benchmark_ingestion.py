"""Benchmark INSERT versus COPY on one machine and verify identical raw table content.

This replaces the local raw snapshot twice. Keep other pipeline processes stopped.
"""

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone

from sqlalchemy import text

from olist.config import ROOT, TABLE_FILES, engine
from olist.ingest import ingest
from olist.quality import run as quality


def fingerprints():
    result = {}
    with engine().connect() as conn:
        for table in sorted(TABLE_FILES):
            digest = hashlib.sha256()
            count = 0
            rows = conn.execution_options(stream_results=True).execute(
                text(f'SELECT to_jsonb(t)::text AS row FROM raw."{table}" t ORDER BY 1')
            )
            for row in rows:
                digest.update(row[0].encode("utf-8") + b"\n")
                count += 1
            result[table] = {"rows": count, "sha256": digest.hexdigest()}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="store_true",
        help="Replace local raw tables with the bundled snapshot for both trials",
    )
    args = parser.parse_args()
    if not args.run:
        parser.error("Read the module description, then pass --run to benchmark.")
    quality()
    trials = []
    with engine().connect() as lock:
        if not lock.execute(text("select pg_try_advisory_lock(782342)")).scalar():
            raise RuntimeError("Another pipeline run is active")
        try:
            for method in ["insert", "copy"]:
                started = time.perf_counter()
                ingest(method=method)
                seconds = time.perf_counter() - started
                trials.append(dict(method=method, seconds=seconds, fingerprints=fingerprints()))
            assert trials[0]["fingerprints"] == trials[1]["fingerprints"], (
                "Content changed between methods"
            )
        finally:
            lock.execute(text("select pg_advisory_unlock(782342)"))
    result = dict(
        measured_at=datetime.now(timezone.utc).isoformat(),
        trials=trials,
        identical_contents=True,
        method="One sequential trial per method on the same source and database; parsing included; fingerprint time excluded; cache/order effects possible.",
    )
    (ROOT / "reports/ingestion_benchmark.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({t["method"]: round(t["seconds"], 2) for t in trials}, indent=2))


if __name__ == "__main__":
    main()
