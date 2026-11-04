<#
.SYNOPSIS
  Publish new podcast episodes and run logs to GitHub Pages.

.DESCRIPTION
  The pipeline (with ENABLE_SPOTIFY=true and the GitHub Pages values in
  .env) writes new MP3s into docs\audio and updates docs\feed.xml, and
  publish_logs.py writes sanitized run logs into docs\logs. This script
  commits and pushes those docs\ changes. It does not commit anything
  else.

  The order matters, and it is the fix for a real stranded-commit bug
  (found 2026-11-04):
    1. Stage docs\audio + docs\feed.xml + docs\logs and commit them
       FIRST. Pulling first fails with "cannot pull with rebase: You
       have unstaged changes", because the pipeline's own new files
       are unstaged changes in docs\ (seen live 2026-10-21).
    2. Pull (rebase, autostashing any other local changes).
    3. Push if - and only if - the local branch is ahead of its
       upstream after the pull. The old script pushed only when the
       current run had staged something, so a commit whose push had
       failed was stranded forever: the next run staged nothing, said
       "No new episodes to publish", and never pushed it. Checking
       "ahead of upstream" after every pull closes that hole: any
       unpushed commit, from this run or an earlier failed push, is
       retried on every run until it lands.

  GitHub Pages then rebuilds https://pivital-az.github.io/oloj-homily-automation/

  Run it after a pipeline run, or call it at the end of your scheduled
  task chain. Requires git credentials for the repo on this laptop
  (a one-time interactive `git push` by hand stores them in Windows
  Credential Manager).

.EXAMPLE
  .\scripts\publish_pages.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
# Pick up PATH changes from winget installs made earlier in this session
# (new tools like ffmpeg/git are registered in the registry before they
# appear in this window's PATH).
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

git add -- "docs/audio" "docs/feed.xml" "docs/logs"
$Staged = git diff --cached --name-only
if ($Staged) {
    $Stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
    $HasEpisodes = $Staged -match "docs/audio|docs/feed\.xml"
    if ($HasEpisodes) {
        $Message = "Publish homily episode(s) $Stamp"
        if ($Staged -match "docs/logs") { $Message = "Publish homily episode(s) + run log(s) $Stamp" }
    } else {
        $Message = "Publish run log(s) $Stamp"
    }
    git commit -m $Message | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git commit failed - resolve it by hand, then re-run." }
}

git pull --rebase --autostash --quiet
if ($LASTEXITCODE -ne 0) { throw "git pull failed - resolve it by hand, then re-run." }

# Retriable push: after the pull, is this branch ahead of upstream?
# This is what rescues a commit stranded by an earlier failed push.
$Ahead = 0
try {
    $Ahead = [int](git rev-list --count "@{upstream}..HEAD" 2>$null)
} catch {
    # No upstream configured (e.g. a fresh clone never pushed from):
    # fall back to pushing whenever this run staged something.
    if ($Staged) { $Ahead = 1 }
}

if ($Ahead -eq 0) {
    Write-Host "Nothing new to publish."
    exit 0
}

git push
if ($LASTEXITCODE -ne 0) {
    throw "git push failed - the commit is still on this laptop and the next run will retry it (see the ahead-of-upstream check above)."
}

if ($Staged) {
    Write-Host "Published to GitHub Pages: $($Staged -join ', ')" -ForegroundColor Green
} else {
    Write-Host "Published previously stranded commit(s) to GitHub Pages." -ForegroundColor Green
}
Write-Host "Feed: https://pivital-az.github.io/oloj-homily-automation/feed.xml"
Write-Host "Run logs: https://pivital-az.github.io/oloj-homily-automation/logs/"
