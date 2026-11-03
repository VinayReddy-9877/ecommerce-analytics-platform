# Runbook

## First run

Use Python 3.12 and Docker Desktop/Engine with Compose v2. Work from the extracted
`olist-analytics` directory. The archive already includes the original CSVs.

```sh
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
docker compose up -d --wait
olist run
python scripts/build_snapshot.py
pytest -q
streamlit run dashboards/app.py
```

Open http://localhost:8501. To inspect results without a database, run Streamlit
against the included reports or open `reports/dashboard_snapshot.html` directly.
For a clean redownload run `olist download`; an HTML/login response or incomplete
archive fails loudly. Kaggle can change public download access; if it does, obtain
the CSVs from the source page and place them in `data/raw`.

The `.env.example` documents settings. Docker Compose reads a local `.env`, but
Python loads the local .env and passes its settings to dbt. Process environment variables take precedence. Export changed settings in your
shell (PowerShell example: `$env:PGPASSWORD="your-password"`). Default local
credentials work without editing. Do not use those defaults on a public server.

## Commands

| Command | Purpose |
|---|---|
| `olist download` | Fetch all nine original CSVs from Kaggle |
| `olist ingest` | Transactionally load raw snapshot |
| `olist build` | Run dbt build with model and data-test dependencies |
| `olist analyze` | Export marts, anomalies, inference and forecast |
| `olist report` | Produce a deterministic weekly Markdown report |
| `olist run` | Source quality gate → COPY ingest → dbt build → analysis → delivery diagnostics → report → Excel |
| `olist run --cutoff 2018-06-30 --reporting-end 2018-06-30` | Rebuild an earlier retrospective cohort snapshot |
| `olist report --llm` | Explicit optional paid API call; requires OPENAI_API_KEY and OPENAI_MODEL |

A database session advisory lock rejects overlapping `olist run` executions.
Run individual component commands serially on one workstation. The workflow's concurrency group
prevents overlapping jobs on the same branch. Separate environments should use
separate databases: staging/intermediate/marts schema names are fixed.

## Failure handling

- Import fails: raw tables roll back together; inspect the logged filename.
- dbt fails: do not use the warehouse as a newly approved snapshot; downstream
  analysis/reporting stop. dbt materializations are per model, not one global
  transaction. A successful full rerun restores consistency.
- API fails: deterministic report is retained; the command fails, so no successful
  AI completion is claimed. Retry after checking model access/quota.
- Reports are prior-run files until regenerated; check `last_run.json`, ingestion
  timestamp and cutoff before presenting results. Local exports are not globally
  atomic and should not be read during a run.
- Statistical forecast fails: inspect missing months/history; do not substitute
  invented forecast values.

## GitHub Actions

Create your own repository and push the source. Raw CSVs are ignored by Git;
Actions downloads them. `weekly.yml` runs on pull requests, main-branch pushes,
manual dispatch and Mondays at 03:30 UTC (09:00 IST). It uses a temporary Postgres
service and retains outputs for 90 days. This schedule exists only after the
workflow is installed in your repository; it has not been activated here.

The workflow makes no external LLM calls. A failure alert is sent only when SMTP secrets are configured. To enable an API
step deliberately, add GitHub Secrets, pass them only to a trusted post-test step,
and run `olist report --llm`. Never expose secrets to fork pull requests.

## Optional email delivery

`python scripts/send_report.py --to you@example.com --send` sends the deterministic
report using SMTP over TLS. Without `--send` it only previews the destination and
subject. Set SMTP_HOST, SMTP_PORT (default 465), SMTP_USER, SMTP_PASSWORD and
SMTP_FROM. Only send after reviewing the report; delivery is not exercised in the
supplied validation. Do not put these values in Git.

## Reset

`docker compose down` stops services and retains data. `docker compose down -v`
deletes the local warehouse volume; use only when you intend to rebuild it.

The pipeline also refreshes `reports/operating_review.xlsx`. For publishing, see power_bi.md.

Source contract: data/quality_contract.json. Run history: reports/run_history.csv.
See verification.md for failure injection and controlled ingestion timing.
