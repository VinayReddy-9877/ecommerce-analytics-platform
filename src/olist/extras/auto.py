"""Schema-independent CSV profiling, with explicit optional sales semantics.

Files are profiled independently. No implicit joins, deduplication, or LLM upload.
Each successful run publishes a new immutable directory and a latest pointer.
"""

import csv
import hashlib
import html
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
from plotly.io import to_html


def discover(source):
    source = Path(source).resolve()
    files = [source] if source.is_file() else sorted(source.glob("*.csv"))
    files = [p for p in files if p.suffix.lower() == ".csv"]
    if not files:
        raise ValueError(f"No CSV files found in {source}")
    return files


def fingerprint(files, mapping=None):
    paths = list(files) + ([Path(mapping)] if mapping else [])
    return {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        headers = next(csv.reader(stream), [])
    if not headers or any(not h.strip() for h in headers) or len(set(headers)) != len(headers):
        raise ValueError(f"{path.name}: column names must be non-empty and unique")
    # Preserve identifiers and literal values such as state code NA.
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    return frame.replace(r"^\s*$", pd.NA, regex=True)


def profile(frame):
    columns, charts = [], []
    for name in frame.columns:
        s = frame[name]
        nonnull = s.dropna()
        item = {
            "column": name,
            "missing": int(s.isna().sum()),
            "missing_pct": float(s.isna().mean()) if len(s) else None,
            "distinct": int(nonnull.nunique()),
            "type": "text",
        }
        # Dates require a date-like name AND ISO-style values; ambiguous local dates stay text.
        date_name = re.search(r"date|time|_at$", name, re.I)
        identifier = re.search(r"(^id$|_id$|code|zip|postal|phone)", name, re.I)
        numeric = pd.to_numeric(nonnull, errors="coerce")
        iso_dates = nonnull.str.match(r"^\d{4}-\d{2}-\d{2}(?:[ T].*)?$").all()
        if len(nonnull) and date_name and iso_dates:
            dates = pd.to_datetime(nonnull, errors="coerce", utc=True, format="mixed")
            if dates.notna().all():
                item.update(type="datetime", minimum=str(dates.min()), maximum=str(dates.max()))
                counts = dates.dt.strftime("%Y-%m").value_counts().sort_index()
                charts.append(
                    px.line(
                        x=counts.index,
                        y=counts.values,
                        labels={"x": name, "y": "Rows"},
                        title=f"Rows by month: {name}",
                    )
                )
        elif (
            len(nonnull) and not identifier and numeric.notna().all() and np.isfinite(numeric).all()
        ):
            item.update(
                type="numeric",
                minimum=float(numeric.min()),
                maximum=float(numeric.max()),
                mean=float(numeric.mean()),
                median=float(numeric.median()),
            )
            counts, edges = np.histogram(numeric.astype(float), bins=30)
            labels = [f"{a:.3g} to {b:.3g}" for a, b in zip(edges[:-1], edges[1:])]
            charts.append(
                px.bar(
                    x=labels,
                    y=counts,
                    title=f"Distribution: {name}",
                    labels={"x": name, "y": "Rows"},
                )
            )
        if item["type"] == "text" and 1 < item["distinct"] <= 30:
            counts = nonnull.value_counts().head(12)
            charts.append(
                px.bar(
                    x=counts.index,
                    y=counts.values,
                    title=f"Most frequent: {name}",
                    labels={"x": name, "y": "Rows"},
                )
            )
        columns.append(item)
    result = {
        "rows": len(frame),
        "columns": len(frame.columns),
        "duplicate_rows": int(frame.duplicated().sum()),
        "fields": columns,
    }
    return result, charts[:12]


def sales_analysis(frame, config):
    required = ["order_id", "date", "amount"]
    if config.get("grain") not in ["order", "line"]:
        raise ValueError("Sales mapping grain must be order or line")
    if not isinstance(config.get("currency"), str) or not config["currency"].strip():
        raise ValueError("Sales mapping requires a currency; amounts must use one currency")
    for key in required:
        if config.get(key) not in frame.columns:
            raise ValueError(f"Sales mapping {key!r} must name an existing column")
    data = frame.copy()
    if "status" in config:
        status = config["status"]
        if status not in data or not config.get("include_statuses"):
            raise ValueError("status requires an existing column and include_statuses")
        data = data[data[status].isin(config["include_statuses"])].copy()
    if data.empty:
        raise ValueError("No rows remain for sales analysis")
    if data[config["order_id"]].isna().any():
        raise ValueError("Sales order IDs cannot be blank")
    data["_date"] = pd.to_datetime(
        data[config["date"]], errors="coerce", utc=True, format=config.get("date_format", "ISO8601")
    )
    data["_amount"] = pd.to_numeric(data[config["amount"]], errors="coerce")
    if data["_date"].isna().any() or not np.isfinite(data["_amount"].astype(float)).all():
        raise ValueError(
            "Sales dates/amounts contain missing or invalid values; fix them before rerunning"
        )
    key = config["order_id"]
    if config["grain"] == "order" and data[key].duplicated().any():
        raise ValueError(
            "Duplicate order IDs at order grain; use line grain only for additive line amounts"
        )
    if data.groupby(key)["_date"].nunique().gt(1).any():
        raise ValueError("Each order must have one purchase timestamp")
    orders = data.groupby(key).agg(date=("_date", "first"), amount=("_amount", "sum"))
    result = {
        "currency": config["currency"],
        "orders": len(orders),
        "amount_total": float(orders.amount.sum()),
        "aov": float(orders.amount.mean()),
        "date_start": str(orders.date.min().date()),
        "date_end": str(orders.date.max().date()),
        "amount_definition": config.get("amount_definition", "Sum of the mapped amount column"),
        "grain": config["grain"],
        "status_filter": config.get("include_statuses", "None"),
    }
    if "customer_id" in config:
        customer = config["customer_id"]
        if customer not in data or data[customer].isna().any():
            raise ValueError("Mapped customer IDs must exist and be non-empty")
        if data.groupby(key)[customer].nunique().gt(1).any():
            raise ValueError("Each order must belong to one customer")
        counts = data[[key, customer]].drop_duplicates().groupby(customer).size()
        result.update(customers=len(counts), repeat_customer_rate=float(counts.gt(1).mean()))
    orders["month"] = orders.date.dt.strftime("%Y-%m")
    monthly = orders.groupby("month").agg(orders=("amount", "size"), amount=("amount", "sum"))
    # Reindex missing months, but disclose the complete-snapshot assumption.
    months = pd.period_range(monthly.index.min(), monthly.index.max(), freq="M").astype(str)
    monthly = monthly.reindex(months, fill_value=0).rename_axis("month").reset_index()
    monthly["aov"] = monthly.amount.div(monthly.orders.replace(0, np.nan))
    final_month = orders.date.max().strftime("%Y-%m")
    monthly["eligible_for_comparison"] = monthly.month < final_month
    eligible = monthly[monthly.eligible_for_comparison]
    result["comparison_policy"] = (
        "Exclude the latest observed month. Missing months count as zero; requires a complete source snapshot."
    )
    result["latest_comparable_month"] = None
    result["month_over_month_change"] = None
    if len(eligible) >= 2:
        result["latest_comparable_month"] = eligible.iloc[-1]["month"]
        previous = float(eligible.iloc[-2].amount)
        if previous > 0:
            result["month_over_month_change"] = float(eligible.iloc[-1].amount / previous - 1)
    return result, monthly


def run(source, output, mapping=None):
    files = discover(source)
    output = Path(output).resolve()
    config = json.loads(Path(mapping).read_text()) if mapping else {}
    if config and config.get("file") not in [p.name for p in files]:
        raise ValueError("Mapping file must identify one of the input CSV filenames")
    before = fingerprint(files, mapping)
    prepared = []
    for path in files:
        frame = read_csv(path)
        info, charts = profile(frame)
        info.update(file=path.name, sha256=before[str(path.resolve())])
        monthly = None
        if config.get("file") == path.name:
            info["sales"], monthly = sales_analysis(frame, config)
            charts.insert(
                0,
                px.line(
                    monthly,
                    x="month",
                    y="amount",
                    markers=True,
                    title=f"Monthly mapped amount ({config['currency']})",
                ),
            )
        prepared.append((info, charts, monthly))
    if before != fingerprint(files, mapping):
        raise ValueError("Input changed while reading; rerun after the copy finishes")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    target = output / run_id
    target.mkdir(parents=True)
    results, sections, narrative = (
        [],
        [],
        [
            "# Automatic dataset review",
            "",
            "Files are analyzed independently. Duplicate rows are reported, not removed.",
            "No relationships, units, business causes or financial meanings are inferred.",
            "",
        ],
    )
    for index, (info, charts, monthly) in enumerate(prepared):
        results.append(info)
        title = html.escape(info["file"])
        narrative.extend(
            [
                f"## {info['file']}",
                f"- Rows: {info['rows']:,}.",
                f"- Columns: {info['columns']}; duplicate rows: {info['duplicate_rows']:,}.",
            ]
        )
        section = f"<h2>{title}</h2><p>{info['rows']:,} rows; {info['duplicate_rows']:,} duplicate rows.</p>"
        stats = pd.DataFrame(info["fields"])
        stats.to_csv(target / f"{index + 1:02d}_column_profile.csv", index=False)
        section += stats.to_html(index=False, escape=True, na_rep="")
        if "sales" in info:
            section += (
                "<h3>Mapped sales metrics</h3><pre>"
                + html.escape(json.dumps(info["sales"], indent=2))
                + "</pre>"
            )
            narrative.extend(
                ["", "Mapped sales metrics:", "```json", json.dumps(info["sales"], indent=2), "```"]
            )
            monthly.to_csv(target / "monthly_sales.csv", index=False)
        for chart in charts:
            chart.update_layout(template="plotly_white", height=360)
            section += to_html(chart, full_html=False, include_plotlyjs=False)
        sections.append(section)
        narrative.append("")
    # Bundle Plotly locally; reports work offline and no data goes to an API.
    from plotly.offline import get_plotlyjs

    document = (
        '<!doctype html><meta charset="utf-8"><title>Automatic dataset review</title><style>body{font:16px Arial;color:#183044;max-width:1200px;margin:40px auto;padding:20px}table{border-collapse:collapse;display:block;overflow:auto}td,th{padding:8px;border:1px solid #ddd}pre{white-space:pre-wrap}h2{margin-top:50px}</style><h1>Automatic dataset review</h1><p>Independent CSV profiles. Sales metrics require an explicit mapping. Latest observed month is excluded from comparisons.</p><script>'
        + get_plotlyjs()
        + "</script>"
        + "".join(sections)
    )
    (target / "dashboard.html").write_text(document, encoding="utf-8")
    (target / "report.md").write_text("\n".join(narrative), encoding="utf-8")
    (target / "analysis.json").write_text(
        json.dumps({"run_id": run_id, "files": results}, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    pointer = output / ".latest.tmp"
    pointer.write_text(
        json.dumps({"run_id": run_id, "report": str(target / "dashboard.html")}, indent=2)
    )
    pointer.replace(output / "latest.json")
    return target


def watch(source, output, mapping=None, interval=30):
    if interval < 2:
        raise ValueError("Watch interval must be at least two seconds")
    previous = None
    while True:
        try:
            files = discover(source)
            current = fingerprint(files, mapping)
            if current != previous:
                # A second unchanged scan reduces the chance of reading a partially copied CSV.
                time.sleep(interval)
                if current != fingerprint(discover(source), mapping):
                    continue
                target = run(source, output, mapping)
                print(f"Report ready: {target / 'dashboard.html'}", flush=True)
                previous = current
        except (ValueError, OSError, pd.errors.ParserError) as error:
            print(f"Input not ready: {error}", flush=True)
        time.sleep(interval)
