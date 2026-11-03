import json
import warnings
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from jsonschema import Draft7Validator

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from jsonschema import RefResolver
from olist import excel

ROOT = Path(__file__).parents[1]


def test_powerbi_definitions_match_microsoft_schemas():
    store = {}
    for p in (ROOT / "tests/schemas").glob("*.json"):
        doc = json.loads(p.read_text())
        store["https://developer.microsoft.com/json-schemas/" + p.name.replace("__", "/")] = doc
        if "$id" in doc:
            store[doc["$id"]] = doc
    files = list((ROOT / "dashboards/powerbi/Olist").rglob("*.json"))
    files.append(ROOT / "dashboards/powerbi/Olist/Olist.Report/definition.pbir")
    for p in files:
        doc = json.loads(p.read_text())
        url = doc.get("$schema")
        if not url:
            continue
        schema = store[url]
        resolver = RefResolver(
            base_uri=url, referrer=schema, store=store, handlers={"https": lambda u: store[u]}
        )
        Draft7Validator(schema, resolver=resolver).validate(doc)


def test_powerbi_visual_fields_exist_in_model():
    base = ROOT / "dashboards/powerbi/Olist"
    tables = json.loads((base / "Olist.SemanticModel/model.bim").read_text())["model"]["tables"]
    fields = {t["name"]: {x["name"] for x in t["columns"] + t.get("measures", [])} for t in tables}
    for p in base.rglob("visual.json"):
        v = json.loads(p.read_text())
        for role in v["visual"]["query"]["queryState"].values():
            for projection in role["projections"]:
                field = next(iter(projection["field"].values()))
                assert field["Property"] in fields[field["Expression"]["SourceRef"]["Entity"]]
        assert v["position"]["x"] + v["position"]["width"] <= 1440
        assert v["position"]["y"] + v["position"]["height"] <= 900


def test_excel_refresh_preserves_formulas_charts_and_values():
    path = excel.export_excel()
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    metrics = json.loads((ROOT / "reports/analysis.json").read_text())
    with ZipFile(path) as z:
        assert z.testzip() is None
        assert len([n for n in z.namelist() if "/charts/chart" in n and n.endswith(".xml")]) == 4
        summary = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        cell = summary.find('.//s:c[@r="C5"]', ns)
        assert cell.find("s:f", ns) is not None
        assert float(cell.find("s:v", ns).text) == pytest.approx(metrics["gmv_brl"])
        repeat = ET.fromstring(z.read("xl/worksheets/sheet4.xml"))
        assert repeat.find('.//s:c[@r="E6"]/s:f', ns).text == "D6/C6"
