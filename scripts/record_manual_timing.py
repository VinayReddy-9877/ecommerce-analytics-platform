"""Record a measured manual report duration; never estimate savings from a preset baseline."""

import argparse
import json
from datetime import datetime, timezone

from olist.config import ROOT

parser = argparse.ArgumentParser()
parser.add_argument("--minutes", type=float, required=True)
parser.add_argument(
    "--method", required=True, help="What you actually did, tools used, and matching report outputs"
)
args = parser.parse_args()
if args.minutes <= 0:
    parser.error("Minutes must be a positive stopwatch measurement")
status = json.loads((ROOT / "reports/last_run.json").read_text())
if status.get("status") != "success" or "total_seconds" not in status:
    parser.error("Run the current pipeline successfully before recording a comparison")
result = dict(
    recorded_at=datetime.now(timezone.utc).isoformat(),
    manual_minutes=args.minutes,
    manual_method=args.method,
    automated_run_id=status["run_id"],
    automated_seconds=status["total_seconds"],
    note="User-supplied manual timing. Compare equivalent outputs on the same machine; automation time is sum of timed steps.",
)
(ROOT / "reports/time_comparison.json").write_text(json.dumps(result, indent=2) + "\n")
print("Saved measured comparison to reports/time_comparison.json")
