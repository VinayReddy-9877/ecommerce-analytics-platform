"""Generate a native PBIP report and import-mode semantic model from exported marts.

Run after olist run. Pass --reports-dir on Windows to set the CSV source folder.
The report definition is checked separately against Microsoft's public schemas.
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report/"


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports-dir", default=str(ROOT / "reports"))
    args = parser.parse_args()
    out = ROOT / "dashboards/powerbi/Olist"
    # Aggregated tables intentionally remain separate. Visuals use their own grain.
    specs = {
        "Sales": (
            "daily_sales.csv",
            [
                ("day", "dateTime"),
                ("orders", "int64"),
                ("gmv", "double"),
                ("freight", "double"),
                ("aov", "double"),
            ],
        ),
        "Customers": (
            "customer_rfm.csv",
            [
                ("customer_unique_id", "string"),
                ("recency_days", "int64"),
                ("frequency", "int64"),
                ("monetary_value", "double"),
                ("segment", "string"),
                ("monetary_percentile", "double"),
            ],
        ),
        "Delivery": (
            "delivery_performance.csv",
            [
                ("customer_state", "string"),
                ("delivered_orders", "int64"),
                ("delivery_denominator", "int64"),
                ("late_rate", "double"),
                ("mean_delivery_days", "double"),
                ("late_review_score", "double"),
                ("on_time_review_score", "double"),
            ],
        ),
        "Cohorts": (
            "cohort_retention.csv",
            [
                ("cohort", "dateTime"),
                ("cohort_size", "int64"),
                ("month", "dateTime"),
                ("month_number", "int64"),
                ("active_customers", "int64"),
                ("retention", "double"),
            ],
        ),
        "Repeat": (
            "repeat_delivery_summary.csv",
            [
                ("experience", "string"),
                ("customers", "int64"),
                ("repeat_customers", "int64"),
                ("repeat_rate", "double"),
                ("repeat_rate_30d", "double"),
                ("repeat_rate_60d", "double"),
                ("followup_gmv", "double"),
                ("followup_gmv_per_customer", "double"),
            ],
        ),
        "Sellers": (
            "seller_scorecard.csv",
            [
                ("seller_id", "string"),
                ("orders", "int64"),
                ("gmv", "double"),
                ("mean_order_review_score", "double"),
                ("late_rate", "double"),
                ("state", "string"),
                ("gmv_rank", "int64"),
            ],
        ),
    }
    measures = {
        "Sales": [
            ("GMV BRL", "SUM(Sales[gmv])", '"BRL "#,##0'),
            ("Delivered Orders", "SUM(Sales[orders])", "#,##0"),
            ("AOV BRL", "DIVIDE([GMV BRL],[Delivered Orders])", '"BRL "#,##0.00'),
        ],
        "Customers": [
            ("Buying Customers", "COUNTROWS(Customers)", "#,##0"),
            (
                "Repeat Customer Rate",
                "DIVIDE(CALCULATE(COUNTROWS(Customers),Customers[frequency]>1),COUNTROWS(Customers))",
                "0.00%",
            ),
            ("Customer GMV", "SUM(Customers[monetary_value])", '"BRL "#,##0'),
        ],
        "Delivery": [
            (
                "Late Rate",
                "DIVIDE(SUMX(Delivery,Delivery[late_rate]*Delivery[delivery_denominator]),SUM(Delivery[delivery_denominator]))",
                "0.00%",
            ),
            (
                "Mean Delivery Days",
                "DIVIDE(SUMX(Delivery,Delivery[mean_delivery_days]*Delivery[delivery_denominator]),SUM(Delivery[delivery_denominator]))",
                "0.0",
            ),
        ],
        "Repeat": [
            (
                "Repeat Within 90 Days",
                "DIVIDE(SUM(Repeat[repeat_customers]),SUM(Repeat[customers]))",
                "0.00%",
            ),
            (
                "Followup GMV Per Customer",
                "DIVIDE(SUM(Repeat[followup_gmv]),SUM(Repeat[customers]))",
                '"BRL "0.00',
            ),
        ],
        "Cohorts": [
            (
                "Cohort Retention",
                "DIVIDE(SUM(Cohorts[active_customers]),SUM(Cohorts[cohort_size]))",
                "0.00%",
            )
        ],
    }
    tables = []
    for table, (file, columns) in specs.items():
        types = {
            "string": "type text",
            "int64": "Int64.Type",
            "double": "type number",
            "dateTime": "type datetime",
        }
        mtypes = ", ".join('{"' + name + '", ' + types[kind] + "}" for name, kind in columns)
        expression = [
            "let",
            f'    Source = Csv.Document(File.Contents(SourceFolder & "/{file}"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
            "    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
            f'    Typed = Table.TransformColumnTypes(Headers, {{{mtypes}}}, "en-US")',
            "in",
            "    Typed",
        ]
        tables.append(
            {
                "name": table,
                "columns": [
                    {"name": n, "dataType": t, "sourceColumn": n, "summarizeBy": "none"}
                    for n, t in columns
                ],
                "measures": [
                    {"name": n, "expression": e, "formatString": f}
                    for n, e, f in measures.get(table, [])
                ],
                "partitions": [
                    {
                        "name": table,
                        "mode": "import",
                        "source": {"type": "m", "expression": expression},
                    }
                ],
            }
        )
    write(
        out / "Olist.SemanticModel/model.bim",
        {
            "name": "Olist",
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "sourceQueryCulture": "en-US",
                "tables": tables,
                "expressions": [
                    {
                        "name": "SourceFolder",
                        "kind": "m",
                        "expression": json.dumps(args.reports_dir.replace("\\", "/"))
                        + ' meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
                    }
                ],
            },
        },
    )
    write(out / "Olist.SemanticModel/definition.pbism", {"version": "1.0", "settings": {}})
    write(
        out / "Olist.pbip",
        {
            "version": "1.0",
            "artifacts": [{"report": {"path": "Olist.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    write(
        out / "Olist.Report/definition.pbir",
        {
            "$schema": BASE + "definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": "../Olist.SemanticModel"}},
        },
    )
    definition = out / "Olist.Report/definition"
    write(
        definition / "version.json",
        {"$schema": BASE + "definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"},
    )
    write(
        definition / "report.json",
        {
            "$schema": BASE + "definition/report/1.0.0/schema.json",
            "layoutOptimization": "None",
            "themeCollection": {},
        },
    )
    names = ["executive", "customers", "operations"]
    write(
        definition / "pages/pages.json",
        {
            "$schema": BASE + "definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": names,
            "activePageName": "executive",
        },
    )
    for name in names:
        write(
            definition / f"pages/{name}/page.json",
            {
                "$schema": BASE + "definition/page/1.0.0/schema.json",
                "name": name,
                "displayName": name.title(),
                "displayOption": "FitToPage",
                "height": 900,
                "width": 1440,
            },
        )

    def field(table, name, measure=False):
        kind = "Measure" if measure else "Column"
        return {
            "field": {kind: {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}},
            "queryRef": table + "." + name,
            "nativeQueryRef": name,
        }

    def visual(page, name, kind, title, roles, x, y, w, h):
        v = {
            "$schema": BASE + "definition/visualContainer/2.0.0/schema.json",
            "name": name,
            "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0},
            "visual": {
                "visualType": kind,
                "query": {
                    "queryState": {
                        role: {"projections": [field(*entry) for entry in entries]}
                        for role, entries in roles.items()
                    }
                },
                "visualContainerObjects": {
                    "title": [
                        {
                            "properties": {
                                "show": {"expr": {"Literal": {"Value": "true"}}},
                                "text": {
                                    "expr": {
                                        "Literal": {"Value": "'" + title.replace("'", "''") + "'"}
                                    }
                                },
                            }
                        }
                    ]
                },
                "drillFilterOtherVisuals": True,
            },
        }
        write(definition / f"pages/{page}/visuals/{name}/visual.json", v)

    for i, measure in enumerate(["GMV BRL", "Delivered Orders", "AOV BRL"]):
        visual(
            "executive",
            "kpi" + str(i),
            "card",
            measure,
            {"Values": [("Sales", measure, True)]},
            30 + i * 460,
            30,
            430,
            140,
        )
    visual(
        "executive",
        "salestrend",
        "lineChart",
        "Delivered merchandise GMV by purchase date",
        {"Category": [("Sales", "day")], "Y": [("Sales", "GMV BRL", True)]},
        30,
        200,
        1380,
        500,
    )
    visual(
        "executive",
        "datefilter",
        "slicer",
        "Purchase date (Executive page)",
        {"Values": [("Sales", "day")]},
        30,
        730,
        1380,
        130,
    )
    for i, measure in enumerate(["Buying Customers", "Repeat Customer Rate"]):
        visual(
            "customers",
            "customerkpi" + str(i),
            "card",
            measure,
            {"Values": [("Customers", measure, True)]},
            30 + i * 460,
            30,
            430,
            130,
        )
    visual(
        "customers",
        "segment",
        "clusteredColumnChart",
        "Merchandise value by RFM segment",
        {"Category": [("Customers", "segment")], "Y": [("Customers", "Customer GMV", True)]},
        30,
        190,
        650,
        290,
    )
    visual(
        "customers",
        "repeat",
        "clusteredColumnChart",
        "90-day repeat rate after first delivery",
        {"Category": [("Repeat", "experience")], "Y": [("Repeat", "Repeat Within 90 Days", True)]},
        710,
        190,
        700,
        290,
    )
    visual(
        "customers",
        "cohorts",
        "pivotTable",
        "Monthly retention (cohort x months since first purchase)",
        {
            "Rows": [("Cohorts", "cohort")],
            "Columns": [("Cohorts", "month_number")],
            "Values": [("Cohorts", "Cohort Retention", True)],
        },
        30,
        510,
        1380,
        340,
    )
    visual(
        "operations",
        "latekpi",
        "card",
        "Late deliveries / eligible deliveries",
        {"Values": [("Delivery", "Late Rate", True)]},
        30,
        30,
        600,
        130,
    )
    visual(
        "operations",
        "states",
        "clusteredColumnChart",
        "Late share by customer state",
        {"Category": [("Delivery", "customer_state")], "Y": [("Delivery", "Late Rate", True)]},
        30,
        190,
        1380,
        300,
    )
    visual(
        "operations",
        "sellers",
        "tableEx",
        "Seller scorecard (whole-order reviews)",
        {
            "Values": [
                ("Sellers", x)
                for x in [
                    "seller_id",
                    "state",
                    "orders",
                    "gmv",
                    "late_rate",
                    "mean_order_review_score",
                ]
            ]
        },
        30,
        520,
        1380,
        330,
    )
    from powerbi_star import upgrade

    upgrade(out)
    print(out / "Olist.pbip")


if __name__ == "__main__":
    main()
