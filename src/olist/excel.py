"""Refresh the authored Excel template while preserving its tables and charts.

Only known numeric inputs and cached summary results are replaced. Formulas
remain editable and Excel recalculates them on opening. No macros are used.
"""

import json
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from .config import ROOT

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def workbook_inputs():
    reports = ROOT / "reports"
    monthly = pd.read_csv(reports / "monthly_sales.csv").sort_values("month")
    delivery = pd.read_csv(reports / "delivery_performance.csv").sort_values("customer_state")
    repeat = pd.read_csv(reports / "repeat_delivery_summary.csv")
    metrics = json.loads((reports / "analysis.json").read_text())
    return {
        "metrics": metrics,
        "monthly": json.loads(monthly.to_json(orient="records")),
        "delivery": json.loads(delivery.to_json(orient="records")),
        "repeat": json.loads(repeat.to_json(orient="records")),
    }


def export_excel():
    template = ROOT / "dashboards/excel/operating_review_template.xlsx"
    if not template.exists():
        raise FileNotFoundError(
            "Excel template is missing; restore dashboards/excel from the project archive."
        )
    data = workbook_inputs()
    m = data["metrics"]
    updates = {
        "Summary": {
            "B3": f"Purchase cutoff: {m['cutoff']}; comparisons through {m['reporting_end']}",
            "C8": m["customers"],
            "C9": m["repeat_customer_rate"],
        },
        "Monthly": {},
        "Delivery": {},
        "Repeat": {},
    }
    for i, row in enumerate(data["monthly"], 6):
        for col, key in zip("BCDE", ["month", "orders", "gmv", "aov"]):
            updates["Monthly"][f"{col}{i}"] = (
                (pd.Timestamp(row[key]) - pd.Timestamp("1899-12-30")).days
                if key == "month"
                else row[key]
            )
    # Fixed 24-row template includes the complete default history. Shorter runs clear the tail.
    for i in range(6 + len(data["monthly"]), 30):
        for col in "BCDE":
            updates["Monthly"][f"{col}{i}"] = "" if col == "B" else 0
    for i, row in enumerate(data["delivery"], 6):
        for col, key in zip(
            "BCDEF",
            [
                "customer_state",
                "delivered_orders",
                "delivery_denominator",
                "late_rate",
                "mean_delivery_days",
            ],
        ):
            updates["Delivery"][f"{col}{i}"] = row[key]
    for i, row in enumerate(data["repeat"], 6):
        for col, key in zip(
            "BCDEF",
            [
                "experience",
                "customers",
                "repeat_customers",
                "repeat_rate",
                "followup_gmv_per_customer",
            ],
        ):
            updates["Repeat"][f"{col}{i}"] = row[key]
    caches = {
        "Summary": {
            "C5": m["gmv_brl"],
            "C6": m["delivered_orders"],
            "C7": m["aov_brl"],
            "C10": m["late_rate"],
        }
    }
    for i, row in enumerate(data["monthly"], 6):
        caches.setdefault("Monthly", {})[f"F{i}"] = pd.Timestamp(row["month"]).strftime("%b %y")
    for address in ["E6", "E7"]:
        caches.setdefault("Repeat", {})[address] = updates["Repeat"].pop(address)
    destination = ROOT / "reports/operating_review.xlsx"
    with ZipFile(template) as source, ZipFile(destination, "w", ZIP_DEFLATED) as out:
        wb = ET.fromstring(source.read("xl/workbook.xml"))
        rels = ET.fromstring(source.read("xl/_rels/workbook.xml.rels"))
        paths = {el.attrib["Id"]: el.attrib["Target"] for el in rels}
        mapping = {}
        for sh in wb.find("s:sheets", NS):
            target = paths[
                sh.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            ]
            path = target.lstrip("/") if target.startswith("/") else "xl/" + target
            mapping[path] = sh.attrib["name"]
        for item in source.infolist():
            content = source.read(item.filename)
            name = mapping.get(item.filename)
            if name in updates:
                root = ET.fromstring(content)
                for cell in root.findall(".//s:sheetData/s:row/s:c", NS):
                    address = cell.attrib["r"]
                    if address in updates[name]:
                        value = updates[name][address]
                        if value is None:
                            value = ""
                        for child in list(cell):
                            cell.remove(child)
                        if isinstance(value, str):
                            cell.set("t", "inlineStr")
                            inline = ET.SubElement(cell, "{" + NS["s"] + "}is")
                            ET.SubElement(inline, "{" + NS["s"] + "}t").text = value
                        else:
                            cell.attrib.pop("t", None)
                            ET.SubElement(cell, "{" + NS["s"] + "}v").text = str(value)
                    elif address in caches.get(name, {}):
                        old = cell.find("s:v", NS)
                        if old is None:
                            old = ET.SubElement(cell, "{" + NS["s"] + "}v")
                        cached = caches[name][address]
                        if isinstance(cached, str):
                            cell.set("t", "str")
                        old.text = str(cached)
                content = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            out.writestr(item, content)
    return destination
