"""Bounded, local file analysis. Business semantics are supplied by the user."""

import csv
import io
import zipfile

import pandas as pd

from .auto import sales_analysis


def read_upload(name, payload):
    if len(payload) > 50 * 1024**2:
        raise ValueError("Maximum file size is 50 MiB.")
    if name.lower().endswith(".csv"):
        text = payload.decode("utf-8-sig")
        headers = next(csv.reader(io.StringIO(text)), [])

        def reader():
            return pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False, nrows=500001)
    elif name.lower().endswith(".xlsx"):
        from openpyxl import load_workbook

        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if sum(i.file_size for i in archive.infolist()) > 200 * 1024**2:
                raise ValueError("Expanded workbook exceeds 200 MiB.")
        book = load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
        try:
            rows = book.worksheets[0].iter_rows(values_only=True)
            headers = [str(v) if v is not None else "" for v in next(rows, ())]
            records = []
            for row in rows:
                if len(records) >= 500000:
                    raise ValueError("Maximum is 500,000 rows.")
                records.append([str(v) if v is not None else "" for v in row])
            frame = pd.DataFrame(records, columns=headers)
        finally:
            book.close()

        def reader():
            return frame
    else:
        raise ValueError("Upload UTF-8 CSV or XLSX.")
    if not headers or any(not h.strip() for h in headers) or len(set(headers)) != len(headers):
        raise ValueError("Column headers must be non-empty and unique.")
    result = reader()
    if len(result) > 500000:
        raise ValueError("Maximum is 500,000 rows.")
    if len(result.columns) > 200:
        raise ValueError("Maximum is 200 columns.")
    return result.replace(r"^\s*$", pd.NA, regex=True)


def analyze_mapped(frame, mapping):
    metrics, monthly = sales_analysis(frame, mapping)
    data = frame.copy()
    if mapping.get("status"):
        data = data[data[mapping["status"]].isin(mapping["include_statuses"])]
    key = mapping["order_id"]
    data["_date"] = pd.to_datetime(
        data[mapping["date"]], format=mapping.get("date_format", "ISO8601"), utc=True
    )
    data["_amount"] = pd.to_numeric(data[mapping["amount"]])
    orders = data.groupby(key).agg(date=("_date", "first"), amount=("_amount", "sum"))
    tables = {"monthly": monthly}
    for semantic in ("customer_id", "delivered", "estimated", "state"):
        column = mapping.get(semantic)
        if column:
            if data.groupby(key)[column].nunique(dropna=False).gt(1).any():
                raise ValueError(f"Each order must have one {semantic} value.")
            orders[semantic] = data.groupby(key)[column].first()
    if "customer_id" in orders:
        customers = orders.groupby("customer_id").agg(
            frequency=("amount", "size"),
            monetary_value=("amount", "sum"),
            last_purchase=("date", "max"),
            first_purchase=("date", "min"),
        )
        customers["recency_days"] = (orders.date.max() - customers.last_purchase).dt.days
        customers["segment"] = customers.frequency.map(
            lambda n: "Repeat buyer" if n > 1 else "One-time buyer"
        )
        tables["customers"] = customers.reset_index()
        work = orders.copy()
        work["month"] = work.date.dt.tz_localize(None).dt.to_period("M")
        work["cohort"] = work.customer_id.map(work.groupby("customer_id").month.min())
        work["month_number"] = (
            (work.month.dt.year - work.cohort.dt.year) * 12
            + work.month.dt.month
            - work.cohort.dt.month
        )
        counts = work.groupby(["cohort", "month_number"]).customer_id.nunique()
        sizes = work.groupby("cohort").customer_id.nunique()
        rows = []
        for cohort, size in sizes.items():
            for month in range(work.month.max().ordinal - cohort.ordinal + 1):
                rows.append(
                    {
                        "cohort": str(cohort),
                        "month_number": month,
                        "customers": int(counts.get((cohort, month), 0)),
                        "retention": counts.get((cohort, month), 0) / size,
                    }
                )
        tables["cohorts"] = pd.DataFrame(rows)
    if "delivered" in orders and "estimated" in orders:
        actual = pd.to_datetime(
            orders.delivered,
            errors="coerce",
            format=mapping.get("date_format", "ISO8601"),
            utc=True,
        )
        estimated = pd.to_datetime(
            orders.estimated,
            errors="coerce",
            format=mapping.get("date_format", "ISO8601"),
            utc=True,
        )
        valid = (
            actual.notna() & estimated.notna() & actual.ge(orders.date) & estimated.ge(orders.date)
        )
        orders["late"] = (actual.dt.normalize() > estimated.dt.normalize()).where(valid)
        metrics["delivery_eligible_orders"] = int(valid.sum())
        metrics["delivery_excluded_orders"] = int((~valid).sum())
        metrics["late_rate"] = float(orders.loc[valid, "late"].mean()) if valid.any() else None
        if "state" in orders:
            tables["delivery_by_state"] = (
                orders.groupby("state", dropna=False)
                .agg(eligible_orders=("late", "count"), late_rate=("late", "mean"))
                .reset_index()
            )
    return metrics, tables
