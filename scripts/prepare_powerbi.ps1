$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& .\.venv\Scripts\python.exe scripts/build_powerbi.py --reports-dir (Join-Path (Get-Location) 'reports')
if ($LASTEXITCODE -ne 0) { throw 'Power BI preparation failed.' }
Start-Process .\dashboards\powerbi\Olist\Olist.pbip
