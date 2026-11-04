<#
.SYNOPSIS
  Prepare sanitized run logs for GitHub Pages, then publish them.

.DESCRIPTION
  Runs src\publish_logs.py (copies logs\run-*.log, sanitized, into
  docs\logs with an index page, pruned to the newest 30 runs) and then
  scripts\publish_pages.ps1, which commits and pushes docs\logs.
  Run it by hand any time you want the latest logs online without a
  full pipeline run. run_pipeline.ps1 does both steps automatically
  after every real run, including failed runs.

.EXAMPLE
  .\scripts\publish_logs.ps1
#>
[CmdletBinding()]
param(
    [int]$Keep = 30
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment not found. Run .\scripts\setup_windows.ps1 first."
}

& $VenvPython (Join-Path $RepoRoot "src\publish_logs.py") --keep $Keep
if ($LASTEXITCODE -ne 0) { throw "publish_logs.py failed." }

& (Join-Path $RepoRoot "scripts\publish_pages.ps1")
