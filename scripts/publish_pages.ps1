<#
.SYNOPSIS
  Publish new podcast episodes to GitHub Pages.

.DESCRIPTION
  The pipeline (with ENABLE_SPOTIFY=true and the GitHub Pages values in
  .env) writes new MP3s into docs\audio and updates docs\feed.xml, but
  it does not commit anything. This script does that part:
  pulls, stages only docs\audio + docs\feed.xml, commits and pushes.
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

git pull --rebase --quiet
if ($LASTEXITCODE -ne 0) { throw "git pull failed - resolve it by hand, then re-run." }

git add -- "docs/audio" "docs/feed.xml"
$Staged = git diff --cached --name-only
if (-not $Staged) {
    Write-Host "No new episodes to publish."
    exit 0
}

$Stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
git commit -m "Publish homily episode(s) $Stamp" | Out-Null
git push
if ($LASTEXITCODE -ne 0) { throw "git push failed." }

Write-Host "Published to GitHub Pages: $($Staged -join ', ')" -ForegroundColor Green
Write-Host "Feed: https://pivital-az.github.io/oloj-homily-automation/feed.xml"
