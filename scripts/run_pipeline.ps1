<#
.SYNOPSIS
  Run one pipeline pass (latest Sunday) using the repo virtualenv.
  This is what the scheduled tasks call; it is also safe to run by hand.

.EXAMPLE
  .\scripts\run_pipeline.ps1
  .\scripts\run_pipeline.ps1 -DryRun
  .\scripts\run_pipeline.ps1 -Date 2026-10-18 -Force
#>
[CmdletBinding()]
param(
    [string]$Date,
    [switch]$DryRun,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
# Pick up PATH changes from winget installs made earlier in this session
# (new tools like ffmpeg/git are registered in the registry before they
# appear in this window's PATH).
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment not found. Run .\scripts\setup_windows.ps1 first."
}

$ArgsList = @((Join-Path $RepoRoot "src\main.py"))
if ($Date)   { $ArgsList += @("--date", $Date) }
if ($DryRun) { $ArgsList += "--dry-run" }
if ($Force)  { $ArgsList += "--force" }

& $VenvPython @ArgsList
exit $LASTEXITCODE
