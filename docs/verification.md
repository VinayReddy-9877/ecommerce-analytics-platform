# Verify the project on your machine

## Source gate and failure path

`python scripts/demo_quality_failure.py` injects an invalid date in memory and
exercises the pipeline step runner. It proves that downstream calls stop; it does
not contact a database or send a message. The original CSVs are unchanged.

For a complete local pipeline failure, run `olist run --demo-failure` with Docker
running. The command must exit nonzero at the quality step. A temporary source
copy is used. Run `olist run` afterwards to return the latest status to success.

## Ingestion comparison

With no other run active, execute `python scripts/benchmark_ingestion.py --run`.
It replaces raw tables with the bundled dataset using INSERT and then COPY,
measures each and checks sorted SHA-256 table fingerprints. Parsing is included;
fingerprint time is excluded. One sequential trial is affected by warm caches
and order, so use repeated controlled trials for a firm performance claim.
Run `olist run` afterwards to refresh downstream models and reports.

## Manual comparison

Use a stopwatch while producing the same weekly KPIs, workbook and commentary
manually. Record the actual procedure and time. After a successful full pipeline
run, use `python scripts/record_manual_timing.py --minutes <measured minutes>
--method "describe your actual steps"`. The script does not estimate the manual
baseline. Do not compare a simple manual pivot with a more extensive pipeline.

## Power BI and Excel

Run `python scripts/build_powerbi.py --reports-dir "$PWD/reports"`, then open the
PBIP in Power BI Desktop. Refresh, verify full-window GMV BRL 13,221,498 and
96,478 delivered orders, and inspect all four pages. Test the date filter and
state-to-seller drillthrough. Capture the actual application after refresh.

Open `reports/operating_review.xlsx` in Excel. Check the formulas, cached values
and charts. Capture the actual workbook; a Python-generated preview is not proof
of native Excel rendering. Run the pipeline with an earlier cutoff, reopen the
workbook, and capture the changed totals. Restore the default full run afterwards.

## A 90-second walkthrough

- 0-15s: question, historical data and source grain.
- 15-35s: completed run summary, quality gate and Excel output.
- 35-65s: handoff rates, regional comparison and retention uncertainty.
- 65-80s: a real failure artifact showing downstream steps stopped.
- 80-90s: recommendation and observational limitations.

Record the actual screens and your own explanation. Do not present prepared
charts or a generated animation as a recording of a live workflow.
