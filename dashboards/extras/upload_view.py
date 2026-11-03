"""Upload and analyze CSV or Excel datasets."""

import io
import json
import zipfile

import plotly.express as px
import streamlit as st

from olist.extras.auto import profile
from olist.extras.uploads import analyze_mapped, read_upload


def show_general_analysis(frame):
    st.subheader("Automatic insights")

    missing = frame.isna().sum()
    missing = missing[missing > 0].sort_values(ascending=False)

    if missing.empty:
        st.success("No missing values found.")
    else:
        st.write(f"Missing values found in {len(missing)} columns.")
        st.dataframe(
            missing.head(10).rename("Missing values"),
            use_container_width=True,
        )

    numeric = frame.select_dtypes(include="number")

    if not numeric.empty:
        st.subheader("Numeric summary")
        summary = numeric.describe().T.reset_index()
        summary = summary.rename(columns={"index": "Column"})
        st.dataframe(
            summary[["Column", "count", "mean", "min", "max"]].round(2),
            hide_index=True,
        )

    categories = frame.select_dtypes(include=["object", "string", "category"]).columns.tolist()

    if categories:
        st.subheader("Explore categories")
        column = st.selectbox("Select a column", categories)

        counts = frame[column].fillna("Missing").astype(str).value_counts().head(10)
        st.bar_chart(counts)


def render():
    st.title("Analyze your data")
    st.caption(
        "Upload CSV or Excel files. Maximum 50 MiB per file and "
        "500,000 rows. Excel analysis uses the first sheet."
    )

    uploads = st.file_uploader(
        "Choose datasets",
        type=["csv", "xlsx"],
        accept_multiple_files=True,
    )

    if not uploads:
        st.info("Upload a dataset to explore its quality, statistics, and charts.")
        return

    if sum(file.size for file in uploads) > 100 * 1024**2:
        st.error("Combined uploads must stay below 100 MiB.")
        return

    selected = st.selectbox(
        "Dataset",
        range(len(uploads)),
        format_func=lambda i: uploads[i].name,
    )
    upload = uploads[selected]

    try:
        frame = read_upload(upload.name, upload.getvalue())
        info, charts = profile(frame)
    except (ValueError, UnicodeError, OSError, zipfile.BadZipFile) as exc:
        st.error(str(exc))
        return

    st.subheader(upload.name)

    a, b, c = st.columns(3)
    a.metric("Rows", f"{info['rows']:,}")
    b.metric("Columns", info["columns"])
    c.metric("Duplicate rows", f"{info['duplicate_rows']:,}")

    quality, visual, business = st.tabs(["Quality and preview", "Charts", "Business analysis"])

    with quality:
        st.subheader("Data quality")
        st.dataframe(info["fields"], hide_index=True)

        st.subheader("Data preview")
        st.dataframe(frame.head(100), hide_index=True)

        show_general_analysis(frame)

        report = {
            "dataset": upload.name,
            "quality": info,
            "missing_values": frame.isna().sum().to_dict(),
        }

        st.download_button(
            "Download quality report",
            json.dumps(report, indent=2, default=str),
            "quality.json",
            mime="application/json",
        )

    with visual:
        st.subheader("Automatic charts")

        if not charts:
            st.info("No suitable automatic charts found.")

        for chart in charts:
            st.plotly_chart(chart, width="stretch")

    with business:
        st.subheader("Transaction analysis")
        st.caption(
            "Optional analysis for sales or order datasets. "
            "Select the correct columns before calculating business KPIs. "
            "Amounts should use one currency and represent a complete snapshot."
        )

        with st.form("mapping"):
            fields = [
                ("order_id", "Order ID (required)"),
                ("date", "Purchase date (required)"),
                ("amount", "Amount (required)"),
                ("customer_id", "Customer ID"),
                ("delivered", "Actual delivery date"),
                ("estimated", "Promised delivery date"),
                ("state", "Customer state / region"),
                ("status", "Order status"),
            ]

            mapping = {
                key: st.selectbox(label, [""] + list(frame.columns)) for key, label in fields
            }

            mapping["grain"] = st.selectbox("One row represents", ["order", "line"])
            mapping["currency"] = st.text_input("Currency / amount unit", "BRL")
            mapping["date_format"] = st.text_input("Date format", "ISO8601")

            statuses = st.text_input("Statuses to include (comma separated)")
            submitted = st.form_submit_button("Analyze mapped data")

        if submitted:
            mapping = {key: value for key, value in mapping.items() if value}

            if statuses.strip():
                mapping["include_statuses"] = [
                    value.strip() for value in statuses.split(",") if value.strip()
                ]

            try:
                metrics, tables = analyze_mapped(frame, mapping)

                st.subheader("Business metrics")
                st.json(metrics)

                if "monthly" in tables:
                    st.plotly_chart(
                        px.line(
                            tables["monthly"],
                            x="month",
                            y="amount",
                            markers=True,
                        ),
                        width="stretch",
                    )

                for name, table in tables.items():
                    st.subheader(name.replace("_", " ").title())
                    st.dataframe(table, hide_index=True)

                buffer = io.BytesIO()

                with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("metrics.json", json.dumps(metrics, indent=2))
                    archive.writestr("mapping.json", json.dumps(mapping, indent=2))

                    for name, table in tables.items():
                        archive.writestr(f"{name}.csv", table.to_csv(index=False))

                st.download_button(
                    "Download analysis ZIP",
                    buffer.getvalue(),
                    "dataset_analysis.zip",
                    mime="application/zip",
                    on_click="ignore",
                )

            except (ValueError, KeyError, TypeError) as exc:
                st.error(str(exc))
