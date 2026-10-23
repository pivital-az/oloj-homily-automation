<#
.SYNOPSIS
  Publish new podcast episodes to GitHub Pages.

.DESCRIPTION
  The pipeline (with ENABLE_SPOTIFY=true and the GitHub Pages values in
  .env) writes new MP3s into docs\audio and updates docs\feed.xml, but
  it does not commit anything. This script does that part:
  stages only docs\audio + docs\feed.xml, commits them FIRST, then
  pulls (rebase, autostashing any other local changes) and pushes.
  The order matters: pulling first fails with "cannot pull with
  rebase: You have unstaged changes", because the pipeline's own new
  episodes are unstaged changes in docs\ (seen live 2026-10-21).
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

git add -- "docs/audio" "docs/feed.xml"
$Staged = git diff --cached --name-only
if ($Staged) {
    $Stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
    git commit -m "Publish homily episode(s) $Stamp" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git commit failed - resolve it by hand, then re-run." }
}

git pull --rebase --autostash --quiet
if ($LASTEXITCODE -ne 0) { throw "git pull failed - resolve it by hand, then re-run." }

if (-not $Staged) {
    Write-Host "No new episodes to publish."
    exit 0
}

git push
if ($LASTEXITCODE -ne 0) { throw "git push failed." }

Write-Host "Published to GitHub Pages: $($Staged -join ', ')" -ForegroundColor Green
Write-Host "Feed: https://pivital-az.github.io/oloj-homily-automation/feed.xml"
