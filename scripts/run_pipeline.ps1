<#
.SYNOPSIS
  Run one pipeline pass (latest Sunday) using the repo virtualenv.
  This is what the scheduled tasks call; it is also safe to run by hand.
  Before running it pulls the latest code from GitHub (best effort: a
  failed pull warns and the run continues with the code on disk).

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

# Self-update: pull the latest code before running, so fixes pushed to
# GitHub reach this laptop without anyone remembering a manual pull
# (Stone asked for this 2026-10-23). Best effort only: ANY failure -
# no network, a conflict, git missing - logs a warning and the run
# continues with the code already on disk; a failed update must never
# cost a Sunday its homilies. --autostash sets aside uncommitted local
# changes (e.g. episodes not yet published) and restores them after
# the pull. .env, .models, work\ and state are untracked/gitignored
# and are never touched by a pull. If the pull updates this script
# itself, the current run keeps the already-loaded copy and the new
# one applies from the next run; src\*.py updates apply immediately.
try {
    git pull --rebase --autostash --quiet 2>$null
    if ($LASTEXITCODE -ne 0) { throw "git pull exited $LASTEXITCODE" }
} catch {
    Write-Warning "Self-update skipped ($_) - running with the code already on this laptop."
}

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment not found. Run .\scripts\setup_windows.ps1 first."
}

$ArgsList = @((Join-Path $RepoRoot "src\main.py"))
if ($Date)   { $ArgsList += @("--date", $Date) }
if ($DryRun) { $ArgsList += "--dry-run" }
if ($Force)  { $ArgsList += "--force" }

& $VenvPython @ArgsList
$PipelineExit = $LASTEXITCODE

# After a successful real run, publish any new podcast episodes the
# run wrote into docs\ (GitHub Pages). The publish script no-ops
# cleanly when there is nothing new, and a publish failure must not
# mask the pipeline's own result - the episodes are safe on disk and
# the next run (or a manual publish_pages.ps1) retries the push.
if ($PipelineExit -eq 0 -and -not $DryRun) {
    try {
        & (Join-Path $RepoRoot "scripts\publish_pages.ps1")
        if ($LASTEXITCODE -ne 0) { throw "publish_pages.ps1 exited $LASTEXITCODE" }
    } catch {
        Write-Warning "Podcast publish step failed: $_ - new episodes are in docs\audio on this laptop; run .\scripts\publish_pages.ps1 by hand to retry."
    }
}

exit $PipelineExit
