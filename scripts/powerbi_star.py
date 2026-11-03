"""Upgrade generated report to shared dimensions and separate order/item facts."""

import json
from pathlib import Path


def upgrade(out):
    model_path = out / "Olist.SemanticModel/model.bim"
    document = json.loads(model_path.read_text())
    model = document["model"]

    def table(name, filename, columns, measures=()):
        types = {
            "string": "type text",
            "dateTime": "type datetime",
            "int64": "Int64.Type",
            "double": "type number",
        }
        casts = ", ".join('{"' + n + '", ' + types[t] + "}" for n, t in columns)
        return {
            "name": name,
            "columns": [
                {"name": n, "dataType": t, "sourceColumn": n, "summarizeBy": "none"}
                for n, t in columns
            ],
            "measures": [{"name": n, "expression": e, "formatString": f} for n, e, f in measures],
            "partitions": [
                {
                    "name": name,
                    "mode": "import",
                    "source": {
                        "type": "m",
                        "expression": [
                            "let",
                            f' Source = Csv.Document(File.Contents(SourceFolder & "/{filename}"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
                            " Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
                            f' Typed = Table.TransformColumnTypes(Headers, {{{casts}}}, "en-US")',
                            "in",
                            " Typed",
                        ],
                    },
                }
            ],
        }

    money = '"BRL "#,##0.00'
    sales = table(
        "Sales",
        "bi_orders.csv",
        [
            ("order_id", "string"),
            ("day", "dateTime"),
            ("customer_unique_id", "string"),
            ("customer_state", "string"),
            ("gmv", "double"),
            ("late", "double"),
        ],
        [
            ("GMV BRL", "SUM(Sales[gmv])", money),
            ("Delivered Orders", "COUNTROWS(Sales)", "#,##0"),
            ("AOV BRL", "DIVIDE([GMV BRL],[Delivered Orders])", money),
            ("GMV Previous Month", "CALCULATE([GMV BRL],DATEADD('Calendar'[day],-1,MONTH))", money),
            (
                "GMV MoM",
                "IF(HASONEVALUE('Calendar'[year_month]),DIVIDE([GMV BRL]-[GMV Previous Month],[GMV Previous Month]))",
                "0.0%",
            ),
            ("GMV YTD", "TOTALYTD([GMV BRL],'Calendar'[day])", money),
        ],
    )
    item = table(
        "Items",
        "bi_items.csv",
        [
            ("order_id", "string"),
            ("order_item_id", "int64"),
            ("day", "dateTime"),
            ("seller_id", "string"),
            ("category", "string"),
            ("customer_state", "string"),
            ("price", "double"),
            ("late", "double"),
        ],
        [
            ("Item GMV", "SUM(Items[price])", money),
            ("Seller Orders", "DISTINCTCOUNT(Items[order_id])", "#,##0"),
            (
                "Seller Late Rate",
                "DIVIDE(CALCULATE(DISTINCTCOUNT(Items[order_id]),Items[late]=1),CALCULATE(DISTINCTCOUNT(Items[order_id]),NOT ISBLANK(Items[late])))",
                "0.00%",
            ),
        ],
    )
    dimensions = [
        table(
            "Calendar",
            "dim_calendar.csv",
            [("day", "dateTime"), ("year", "int64"), ("month", "int64"), ("year_month", "string")],
        ),
        table("State", "dim_state.csv", [("customer_state", "string")]),
        table("Seller", "dim_seller.csv", [("seller_id", "string"), ("seller_state", "string")]),
        table("Category", "dim_category.csv", [("category", "string")]),
    ]
    dimensions[0]["dataCategory"] = "Time"
    dimensions[0]["columns"][0]["isKey"] = True
    model["tables"] = (
        [t for t in model["tables"] if t["name"] != "Sales"] + [sales, item] + dimensions
    )
    cohort = next(t for t in model["tables"] if t["name"] == "Cohorts")
    cohort["measures"][0]["expression"] = (
        "IF(ISINSCOPE(Cohorts[cohort]) && ISINSCOPE(Cohorts[month_number]),DIVIDE(SUM(Cohorts[active_customers]),SUM(Cohorts[cohort_size])))"
    )
    model["relationships"] = [
        {
            "name": f"{fact}_{dimension}",
            "fromTable": fact,
            "fromColumn": column,
            "toTable": dimension,
            "toColumn": column,
            "fromCardinality": "many",
            "toCardinality": "one",
            "crossFilteringBehavior": "oneDirection",
            "isActive": True,
        }
        for fact, dimension, column in [
            ("Sales", "Calendar", "day"),
            ("Items", "Calendar", "day"),
            ("Sales", "State", "customer_state"),
            ("Items", "State", "customer_state"),
            ("Delivery", "State", "customer_state"),
            ("Items", "Seller", "seller_id"),
            ("Items", "Category", "category"),
        ]
    ]
    model_path.write_text(json.dumps(document, indent=2))
    base = out / "Olist.Report/definition"

    def field(t, n, measure=False):
        return {
            "field": {
                "Measure" if measure else "Column": {
                    "Expression": {"SourceRef": {"Entity": t}},
                    "Property": n,
                }
            },
            "queryRef": t + "." + n,
            "nativeQueryRef": n,
        }

    def save(path, obj):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, indent=2))

    for p in base.rglob("visual.json"):
        v = json.loads(p.read_text())
        for role in v["visual"]["query"]["queryState"].values():
            for projection in role["projections"]:
                f = next(iter(projection["field"].values()))
                t = f["Expression"]["SourceRef"]["Entity"]
                n = f["Property"]
                if t == "Sales" and n == "day":
                    projection.update(field("Calendar", "day"))
                if t == "Delivery" and n == "customer_state":
                    projection.update(field("State", "customer_state"))
        title = v["visual"]["visualContainerObjects"]["title"][0]["properties"]
        title["fontSize"] = {"expr": {"Literal": {"Value": "14D"}}}
        if v["name"] == "salestrend":
            v["position"]["height"] = 340
        if v["name"] == "datefilter":
            v["position"]["y"] = 740
        save(p, v)
    template = json.loads(next(base.rglob("visual.json")).read_text())

    def visual(page, name, title, entries, y=200, height=600):
        import copy

        v = copy.deepcopy(template)
        v["name"] = name
        v["position"] = {"x": 30, "y": y, "z": 0, "width": 1380, "height": height, "tabOrder": 0}
        v["visual"]["visualType"] = "tableEx"
        v["visual"]["query"]["queryState"] = {
            "Values": {"projections": [field(*e) for e in entries]}
        }
        v["visual"]["visualContainerObjects"]["title"][0]["properties"]["text"] = {
            "expr": {"Literal": {"Value": "'" + title + "'"}}
        }
        save(base / f"pages/{page}/visuals/{name}/visual.json", v)

    visual(
        "executive",
        "monthly",
        "Monthly GMV, MoM and YTD — August is descriptive only",
        [
            ("Calendar", "year_month"),
            ("Sales", "GMV BRL", True),
            ("Sales", "GMV MoM", True),
            ("Sales", "GMV YTD", True),
        ],
        550,
        180,
    )
    entries = [
        ("Seller", "seller_id"),
        ("Seller", "seller_state"),
        ("Items", "Seller Orders", True),
        ("Items", "Item GMV", True),
        ("Items", "Seller Late Rate", True),
    ]
    page = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/1.0.0/schema.json",
        "name": "seller_detail",
        "displayName": "Investigate sellers serving this state",
        "displayOption": "FitToPage",
        "height": 900,
        "width": 1440,
        "pageBinding": {
            "name": "state_to_seller",
            "type": "Drillthrough",
            "parameters": [{"name": "state_parameter", "boundFilter": "state_filter"}],
        },
        "filterConfig": {
            "filters": [
                {
                    "name": "state_filter",
                    "field": field("State", "customer_state")["field"],
                    "type": "Categorical",
                    "howCreated": "Drillthrough",
                }
            ]
        },
    }
    save(base / "pages/seller_detail/page.json", page)
    visual(
        "seller_detail",
        "state_sellers",
        "Order-level lateness shared across sellers; investigate before attributing fault",
        entries,
        30,
        800,
    )
    p = base / "pages/pages.json"
    meta = json.loads(p.read_text())
    meta["pageOrder"].append("seller_detail")
    save(p, meta)
    for name, title in [
        ("executive", "BRL 13.2M delivered merchandise GMV"),
        ("customers", "Repeat purchase is uncommon; test retention campaigns"),
        ("operations", "RJ late rate is about 2.7 times SP"),
    ]:
        p = base / f"pages/{name}/page.json"
        v = json.loads(p.read_text())
        v["displayName"] = title
        save(p, v)


if __name__ == "__main__":
    upgrade(Path(__file__).resolve().parents[1] / "dashboards/powerbi/Olist")
