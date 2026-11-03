"""Persist real runs and copy small deliverables into a dated audit folder."""

import csv
import json
import shutil
from datetime import datetime, timezone


def finalize(output, status):
    status["finished_at"] = datetime.now(timezone.utc).isoformat()
    status["total_seconds"] = round(sum(status["seconds"].values()), 3)
    (output / "last_run.json").write_text(json.dumps(status, indent=2) + "\n")
    fields = [
        "run_id",
        "started_at",
        "cutoff",
        "status",
        "active_step",
        "total_seconds",
        "checks_passed",
        "checks_total",
        "source_rows",
        "seconds",
    ]
    row = {k: status.get(k, "") for k in fields}
    row["seconds"] = json.dumps(status["seconds"], sort_keys=True)
    history = output / "run_history.csv"
    with history.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if f.tell() == 0:
            writer.writeheader()
        writer.writerow(row)
    if status["status"] == "success":
        report = output / "weekly_report.md"
        body = report.read_text(encoding="utf-8")
        summary = (
            f"Checks {status['checks_passed']}/{status['checks_total']} passed | "
            f"Rows {status['source_rows']:,} | Runtime {status['total_seconds']:.1f}s | "
            f"Run {status['run_id']}\n\n"
        )
        report.write_text(summary + body, encoding="utf-8", newline="\n")
    archive = output / "runs" / status["run_id"]
    archive.mkdir(parents=True)
    names = ["last_run.json", "quality_checks.json"]
    if status["status"] == "success":
        names += ["weekly_report.md", "operating_review.xlsx", "analysis.json", "deepdive.json"]
    for name in names:
        if (output / name).exists():
            shutil.copy2(output / name, archive / name)
