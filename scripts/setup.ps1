$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (!(Test-Path .env)) { Copy-Item .env.example .env }
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& .\.venv\Scripts\python.exe -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw 'Project installation failed.' }
docker compose up -d --wait
if ($LASTEXITCODE -ne 0) { throw 'Database startup failed. Check Docker and PGPORT in .env.' }
& .\.venv\Scripts\python.exe -m olist.cli run
if ($LASTEXITCODE -ne 0) { throw 'Pipeline failed. Review the error above.' }
Write-Host 'Complete. Open reports/operating_review.xlsx or run: .\.venv\Scripts\python.exe -m streamlit run dashboards/app.py'
