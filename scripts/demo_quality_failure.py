"""Exercise the real quality gate on a temporary bad source; no database or email needed."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from olist.cli import execute_steps
from olist.config import ROOT
from olist.quality import evaluate


def main():
    contract = json.loads((ROOT / "data/quality_contract.json").read_text())
    original = pd.read_csv
    calls = []

    def corrupted(path, **kwargs):
        frame = original(path, **kwargs)
        if Path(path).name == "olist_orders_dataset.csv":
            idx = frame.index[frame.order_status.eq("delivered")][0]
            frame.loc[idx, "order_delivered_customer_date"] = "2000-01-01 00:00:00"
        return frame

    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp)

        def gate():
            with patch("olist.quality.pd.read_csv", side_effect=corrupted):
                result = evaluate(ROOT / "data/raw", contract)
            (out / "quality_checks.json").write_text(json.dumps(result))
            if result["passed"] != result["total"]:
                raise ValueError("Source quality gate failed: delivery before purchase")
            return result

        status = dict(
            run_id="local-gate-demo",
            started_at=datetime.now(timezone.utc).isoformat(),
            cutoff="2018-07-31",
            status="running",
            seconds={},
        )
        try:
            execute_steps({"quality": gate, "ingest": lambda: calls.append("ingest")}, out, status)
        except ValueError as error:
            status["expected_failure_observed"] = True
            status["message"] = str(error)
        else:
            raise RuntimeError("Failure demo unexpectedly passed")
        assert not calls
        status["downstream_steps_called"] = calls
        status["scope"] = "Local source-gate injection; no PostgreSQL, GitHub Action or email used."
        (ROOT / "reports/local_failure_demo.json").write_text(json.dumps(status, indent=2) + "\n")
        print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
