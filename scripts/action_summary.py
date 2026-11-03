"""Write current run facts to the Actions summary without inventing a success."""

import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / "reports/last_run.json"
if path.exists():
    status = json.loads(path.read_text())
    body = "## Replay result\n\n```json\n" + json.dumps(status, indent=2) + "\n```\n"
else:
    body = "## Replay result\n\nNo pipeline status was produced. Inspect preceding steps.\n"
if os.getenv("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
        f.write(body)
else:
    print(body)
