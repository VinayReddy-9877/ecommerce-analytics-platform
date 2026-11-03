"""Record real CI identity. Never invent a badge result or scheduled event."""

import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
repo = os.getenv("GITHUB_REPOSITORY")
run = os.getenv("GITHUB_RUN_ID")
data = {
    "execution": "github_actions" if run else "local",
    "event": os.getenv("GITHUB_EVENT_NAME", "local"),
    "run_url": f"https://github.com/{repo}/actions/runs/{run}" if repo and run else None,
    "commit": os.getenv("GITHUB_SHA"),
    "scheduled_run_proven": os.getenv("GITHUB_EVENT_NAME") == "schedule",
}
(root / "reports/automation_evidence.json").write_text(json.dumps(data, indent=2))
