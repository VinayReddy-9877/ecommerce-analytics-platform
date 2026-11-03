import json
from pathlib import Path

import pandas as pd
import pytest

from olist.extras.auto import fingerprint, profile, read_csv, run, sales_analysis

EXAMPLE = Path(__file__).parents[1] / "examples/auto"


def test_new_year_sales_and_line_grain():
    data = read_csv(EXAMPLE / "sales.csv")
    mapping = json.loads((EXAMPLE / "mapping.json").read_text())
    result, monthly = sales_analysis(data, mapping)
    assert result["orders"] == 4
    assert result["amount_total"] == 500
    assert result["aov"] == 125
    assert result["repeat_customer_rate"] == pytest.approx(1 / 3)
    assert result["latest_comparable_month"] == "2025-02"
    assert result["month_over_month_change"] == 1
    assert not monthly.iloc[-1].eligible_for_comparison


def test_order_grain_rejects_duplicate_ids():
    mapping = json.loads((EXAMPLE / "mapping.json").read_text())
    mapping["grain"] = "order"
    with pytest.raises(ValueError, match="Duplicate order IDs"):
        sales_analysis(read_csv(EXAMPLE / "sales.csv"), mapping)


def test_generic_data_preserves_ids_and_missing_values(tmp_path):
    p = tmp_path / "inventory.csv"
    p.write_text("product_id,state,quantity\n001,NA,5\n002,SP,\n")
    data = read_csv(p)
    assert data.product_id.tolist() == ["001", "002"]
    assert data.state.iloc[0] == "NA"
    info, _ = profile(data)
    fields = {x["column"]: x for x in info["fields"]}
    assert fields["product_id"]["type"] == "text"
    assert fields["quantity"]["missing"] == 1
    target = run(p, tmp_path / "reports")
    result = json.loads((target / "analysis.json").read_text())
    assert "sales" not in result["files"][0]
    assert (target / "dashboard.html").is_file()


def test_failure_does_not_replace_latest(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("a,b\n1,2\n")
    out = tmp_path / "out"
    run(source, out)
    before = (out / "latest.json").read_text()
    source.write_text("a,a\n1,2\n")
    with pytest.raises(ValueError, match="unique"):
        run(source, out)
    assert (out / "latest.json").read_text() == before


def test_change_detection_includes_mapping(tmp_path):
    p = tmp_path / "mapping.json"
    p.write_text("{}")
    before = fingerprint([EXAMPLE / "sales.csv"], p)
    p.write_text('{"grain":"line"}')
    assert fingerprint([EXAMPLE / "sales.csv"], p) != before


def test_short_history_has_no_fabricated_growth():
    f = pd.DataFrame({"id": ["1"], "date": ["2030-05-01"], "amount": ["0"]})
    result, _ = sales_analysis(
        f, dict(grain="order", currency="USD", order_id="id", date="date", amount="amount")
    )
    assert result["month_over_month_change"] is None
    assert result["latest_comparable_month"] is None


def test_invalid_amount_fails_instead_of_dropping():
    f = pd.DataFrame({"id": ["1"], "date": ["2030-05-01"], "amount": ["unknown"]})
    with pytest.raises(ValueError, match="invalid"):
        sales_analysis(
            f, dict(grain="order", currency="USD", order_id="id", date="date", amount="amount")
        )


def test_watch_reruns_after_file_change(tmp_path, monkeypatch):
    from olist.extras import auto

    source = tmp_path / "input.csv"
    source.write_text("quantity\n1\n")
    runs = []
    real_run = auto.run

    def recording_run(*args):
        result = real_run(*args)
        runs.append(result)
        return result

    ticks = 0

    def tick(_):
        nonlocal ticks
        ticks += 1
        if ticks == 2:
            source.write_text("quantity\n1\n2\n")
        if ticks == 4:
            raise KeyboardInterrupt

    monkeypatch.setattr(auto, "run", recording_run)
    monkeypatch.setattr(auto.time, "sleep", tick)
    with pytest.raises(KeyboardInterrupt):
        auto.watch(source, tmp_path / "out", interval=2)
    assert len(runs) == 2
    assert json.loads((runs[0] / "analysis.json").read_text())["files"][0]["rows"] == 1
    assert json.loads((runs[1] / "analysis.json").read_text())["files"][0]["rows"] == 2
