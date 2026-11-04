<#
.SYNOPSIS
  Run one pipeline pass (latest Sunday, one date, or a date range)
  using the repo virtualenv. This is what the scheduled tasks call;
  it is also safe to run by hand, and it is what the desktop GUI calls.
  Before running it pulls the latest code from GitHub (best effort: a
  failed pull warns and the run continues with the code on disk).

.EXAMPLE
  .\scripts\run_pipeline.ps1
  .\scripts\run_pipeline.ps1 -DryRun
  .\scripts\run_pipeline.ps1 -Date 2026-10-18 -Force
  .\scripts\run_pipeline.ps1 -Start 2026-09-01 -End 2026-09-30 -Force
#>
[CmdletBinding()]
param(
    [string]$Date,
    [string]$Start,
    [string]$End,
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
if ($Start)  { $ArgsList += @("--start", $Start) }
if ($End)    { $ArgsList += @("--end", $End) }
if ($DryRun) { $ArgsList += "--dry-run" }
if ($Force)  { $ArgsList += "--force" }

& $VenvPython @ArgsList
$PipelineExit = $LASTEXITCODE

# Publish after EVERY real run, success or failure - not only after
# success. A failed run's log is the one most worth having offsite,
# and publish_pages.ps1 now retries any commit stranded by an earlier
# failed push, so this step can only help. A publish failure must
# never mask the pipeline's own result: episodes and logs are safe
# on disk, and the next run retries the push.
if (-not $DryRun) {
    try {
        & $VenvPython (Join-Path $RepoRoot "src\publish_logs.py")
        if ($LASTEXITCODE -ne 0) { throw "publish_logs.py exited $LASTEXITCODE" }
    } catch {
        Write-Warning "Run-log preparation failed: $_ - logs are still in logs\ on this laptop; run .\scripts\publish_logs.ps1 by hand to retry."
    }
    try {
        & (Join-Path $RepoRoot "scripts\publish_pages.ps1")
        if ($LASTEXITCODE -ne 0) { throw "publish_pages.ps1 exited $LASTEXITCODE" }
    } catch {
        Write-Warning "Pages publish step failed: $_ - new episodes and logs are in docs\ on this laptop; run .\scripts\publish_pages.ps1 by hand to retry (it retries stranded commits)."
    }
}

exit $PipelineExit
