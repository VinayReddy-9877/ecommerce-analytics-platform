"""Explicit workflow email action; recipient comes only from configured SMTP_TO."""

import os
import subprocess
import sys
from pathlib import Path

recipient = os.environ.get("SMTP_TO")
if not recipient:
    raise SystemExit("Configure SMTP_TO before requesting report delivery.")
subprocess.run(
    [sys.executable, str(Path(__file__).with_name("send_report.py")), "--to", recipient, "--send"],
    check=True,
)
