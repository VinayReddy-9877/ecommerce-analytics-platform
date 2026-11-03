"""Small command surface; dbt remains responsible for SQL dependencies and tests."""

import argparse
import calendar
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import text

from .config import ROOT, engine


def main():
    parser = argparse.ArgumentParser(description="Olist historical analytics pipeline")
    parser.add_argument(
        "command",
        choices=[
            "download",
            "ingest",
            "build",
            "analyze",
            "report",
            "excel",
            "run",
            "auto",
            "deepdive",
            "quality",
        ],
    )
    parser.add_argument("--cutoff", default=os.getenv("ANALYSIS_CUTOFF", "2018-08-31"))
    parser.add_argument("--reporting-end", default=os.getenv("REPORTING_END", "2018-07-31"))
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Call configured OpenAI API; incurs usage charges",
    )
    parser.add_argument("--input", help="CSV file or directory for auto mode")
    parser.add_argument("--output", default=str(ROOT / "reports/custom"))
    parser.add_argument("--mapping", help="Optional explicit sales-column mapping JSON")
    parser.add_argument("--watch", action="store_true", help="Rerun auto mode when inputs change")
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument(
        "--demo-failure",
        action="store_true",
        help="Corrupt a temporary source copy; expect a stopped run",
    )
    args = parser.parse_args()
    if args.demo_failure and args.command != "run":
        parser.error("--demo-failure requires run")
    if args.command == "auto":
        if not args.input:
            parser.error("auto requires --input FILE_OR_DIRECTORY")
        from .extras.auto import run, watch

        try:
            if args.watch:
                watch(args.input, args.output, args.mapping, args.interval)
            else:
                target = run(args.input, args.output, args.mapping)
                print(f"Report ready: {target / 'dashboard.html'}")
        except (ValueError, OSError) as error:
            parser.error(str(error))
        except KeyboardInterrupt:
            print("Stopped watching.")
        return
    try:
        cutoff = date.fromisoformat(args.cutoff)
    except ValueError:
        parser.error("Cutoff must be an ISO date: YYYY-MM-DD")
    if not date(2017, 12, 31) <= cutoff <= date(2018, 8, 31):
        parser.error("Use a month-end cutoff from 2017-12-31 through 2018-08-31")
    if cutoff.day != calendar.monthrange(cutoff.year, cutoff.month)[1]:
        parser.error("Cutoff must be a month end")
    reporting_end = date.fromisoformat(args.reporting_end)
    if reporting_end > cutoff or reporting_end > date(2018, 7, 31):
        parser.error("reporting-end must be <= cutoff and <= 2018-07-31")
    if reporting_end.day != calendar.monthrange(reporting_end.year, reporting_end.month)[1]:
        parser.error("reporting-end must be a month end")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from .analysis import analyze
    from .deepdive import run as deepdive
    from .download import download
    from .excel import export_excel
    from .ingest import ingest
    from .quality import run as quality
    from .report import write_report

    def build():
        subprocess.run(
            [
                str(Path(sys.executable).parent / ("dbt.exe" if os.name == "nt" else "dbt")),
                "build",
                "--project-dir",
                str(ROOT / "dbt_project"),
                "--profiles-dir",
                str(ROOT / "dbt_project"),
                "--vars",
                json.dumps({"cutoff": args.cutoff, "reporting_end": args.reporting_end}),
            ],
            check=True,
        )

    steps = {
        "quality": quality,
        "deepdive": deepdive,
        "download": download,
        "ingest": ingest,
        "build": build,
        "analyze": lambda: analyze(args.reporting_end),
        "excel": export_excel,
        "report": lambda: write_report(args.llm),
    }
    if args.command != "run":
        steps[args.command]()
        return
    output = ROOT / "reports"
    output.mkdir(exist_ok=True)
    status = {
        "command": "run",
        "cutoff": args.cutoff,
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "seconds": {},
    }
    status["run_id"] = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    )
    status["checks_passed"] = 0
    status["checks_total"] = 0
    status["source_rows"] = 0
    # Keep failure injection away from the original source files.
    with tempfile.TemporaryDirectory(prefix="olist-demo-") as temporary:
        if args.demo_failure:
            import pandas as pd

            source = Path(temporary) / "raw"
            shutil.copytree(ROOT / "data/raw", source)
            path = source / "olist_orders_dataset.csv"
            frame = pd.read_csv(path, dtype=str)
            index = frame.index[frame.order_status.eq("delivered")][0]
            frame.loc[index, "order_delivered_customer_date"] = "2000-01-01 00:00:00"
            frame.to_csv(path, index=False)
            steps["quality"] = lambda: quality(source)
            steps["ingest"] = lambda: ingest(source)
        with engine().connect() as lock:
            if not lock.execute(text("select pg_try_advisory_lock(782342)")).scalar():
                raise RuntimeError("Another pipeline run is active in this database")
            try:
                execute_steps(steps, output, status)
            finally:
                lock.execute(text("select pg_advisory_unlock(782342)"))


def execute_steps(steps, output, status):
    """Stop at the first error, preserving its step and duration in the run history."""
    from .runlog import finalize

    try:
        for name in ["quality", "ingest", "build", "analyze", "deepdive", "report", "excel"]:
            status["active_step"] = name
            (output / "last_run.json").write_text(json.dumps(status, indent=2))
            started = time.perf_counter()
            try:
                result = steps[name]()
                if name == "quality":
                    status.update(
                        checks_passed=result["passed"],
                        checks_total=result["total"],
                        source_rows=result["rows"],
                    )
                elif name == "build":
                    path = ROOT / "dbt_project/target/run_results.json"
                    results = json.loads(path.read_text())["results"]
                    tests = [r for r in results if r["unique_id"].startswith("test.")]
                    status["checks_total"] += len(tests)
                    status["checks_passed"] += sum(r["status"] == "pass" for r in tests)
            finally:
                status["seconds"][name] = round(time.perf_counter() - started, 3)
        status["status"] = "success"
    except Exception as error:
        status["status"] = "failed"
        status["error_type"] = type(error).__name__
        if status["active_step"] == "quality" and (output / "quality_checks.json").exists():
            q = json.loads((output / "quality_checks.json").read_text())
            status.update(checks_passed=q["passed"], checks_total=q["total"], source_rows=q["rows"])
        raise
    finally:
        finalize(output, status)


if __name__ == "__main__":
    main()
