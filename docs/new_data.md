# Upload CSV or Excel through the dashboard

Start `streamlit run dashboards/app.py`, then choose **Workspace > Upload data**.
Quality profiling is automatic. Business metrics require explicit column mapping and one currency.
The XLSX reader uses the first worksheet and cached formula values. Recalculate and save in Excel before uploading.
Files stay separate; uploading unrelated tables does not imply valid joins or Olist-specific analysis.

# Analyze another dataset

The new `auto` command is independent of the Olist warehouse. It accepts a CSV
file or a folder of CSVs without Docker, PostgreSQL, dbt, an API key, or fixed dates.
The existing `run` command still operates the Olist-specific nine-table warehouse.

## First run

From the project folder, with the Python environment installed:

```powershell
.\.venv\Scripts\python.exe -m olist.cli auto --input ".\data\incoming\my_data.csv"
```

The terminal prints the path of `dashboard.html`. Open it in a browser. Each run
creates a dated folder under `reports/custom`, containing:

- `dashboard.html`: offline charts, quality metrics and column summaries.
- `report.md`: readable summary of each input file.
- `analysis.json`: machine-readable metrics and input SHA-256 hashes.
- `*_column_profile.csv`: missingness, distinct counts, types and numeric summaries.
- `monthly_sales.csv`: generated when a sales mapping is supplied.

`reports/custom/latest.json` points to the latest successful run. Failed input
validation leaves that pointer unchanged. Earlier successful outputs are retained.
There is no automatic cleanup, so delete old run folders when you no longer need them.

## Automatically rerun after adding or changing files

Create a folder for input CSVs and keep the following terminal running:

```powershell
New-Item -ItemType Directory -Force .\data\incoming
.\.venv\Scripts\python.exe -m olist.cli auto --input ".\data\incoming" --watch --interval 30
```

The watcher hashes the inputs, waits for two matching scans, and runs when a file
is added, removed or changed. It checks only CSVs directly inside that folder.
Press Ctrl+C to stop. It stops when the terminal closes or the laptop shuts down;
this is not an installed background service. Copy files under a temporary extension
and rename them to `.csv` when complete for more reliable ingestion.

Every file is profiled independently. A folder does not imply that its files can
be joined or concatenated. Updated snapshots should replace the corresponding
input file; monthly partitions need consolidation before mapped sales analysis.
Use `--output` to choose a separate results location.

## Revenue and customer metrics require a column mapping

Profiling works on inventory, marketing, support, sales and other tabular datasets.
Business semantics cannot safely be inferred from a number column. For sales,
copy `examples/auto/mapping.json` and change its column names to match your CSV.
The example CSV is a small **synthetic test fixture**, not another real dataset.

```powershell
.\.venv\Scripts\python.exe -m olist.cli auto --input ".\examples\auto\sales.csv" --mapping ".\examples\auto\mapping.json"
```

The example produces 4 delivered orders, BRL 500 total, BRL 125 AOV, and a 33.33%
observed repeat-customer share. Its dates are in 2025, demonstrating that this
mode does not depend on Olist's 2018 window.

Mapping fields:

| Field | Meaning |
|---|---|
| `file` | Exact CSV filename to analyze as sales |
| `grain` | `order` for one row per order, or `line` for additive line amounts |
| `order_id` | Order identifier column |
| `date` | Purchase timestamp column |
| `date_format` | Optional explicit format, such as `%d/%m/%Y`; default ISO 8601 |
| `amount` | Numeric amount column; do not map a repeated order total at line grain |
| `amount_definition` | What the amount actually measures |
| `currency` | One currency shared by all rows; no conversion is performed |
| `customer_id` | Optional customer identifier column |
| `status` / `include_statuses` | Optional status column and included values |

At order grain, duplicate order IDs fail validation. At line grain, amounts are
summed per order before calculating AOV or customer repeat rates. An order must
have one purchase timestamp and one customer. Missing/invalid mapped amounts and
dates fail rather than silently changing the denominator. Duplicate source rows
are flagged, not automatically deleted. Currency symbols and thousands separators
must be cleaned from numeric amount fields before mapping.

## Date handling and limits

Dates come from the new input. Monthly comparisons exclude its latest observed
month, which may be incomplete. At least two earlier months and a positive prior
amount are required for a growth percentage. Missing months count as zero under
a complete-snapshot assumption. This policy does not prove source completeness.
Repeat rate is across the observed window; it is not equal-follow-up retention.

Generic profiling recognizes ISO-style dates in date/time-named columns and
numeric columns whose nonblank values all parse. Identifier-like columns stay
text. Mixed or ambiguous columns remain text. Input must be comma-delimited UTF-8
CSV with unique, nonblank headers and should fit in memory.

There are no guessed cross-file joins, causal explanations, forecasts, or automatic
Power BI/Excel-template modifications in this mode. The Olist-specific dbt models,
90-day delivery analysis and Excel workbook remain available through `olist run`.
Adapting those to a different business requires an explicit source model.

Reports stay local. No LLM API call is made by `auto`.
