<#
.SYNOPSIS
  Cold-start bootstrap for a Windows laptop that does NOT have git yet.

.DESCRIPTION
  Solves the chicken-and-egg problem: you cannot `git clone` this repo
  to run its setup script if git is not installed, and the setup script
  is inside the repo. This script is small enough to fetch on its own
  with plain PowerShell (which Windows always has):

    Invoke-WebRequest -Uri "https://raw.githubusercontent.com/pivital-az/oloj-homily-automation/main/scripts/bootstrap_windows.ps1" -OutFile "$HOME\bootstrap_windows.ps1"
    powershell -ExecutionPolicy Bypass -File "$HOME\bootstrap_windows.ps1"

  What it does, in order:
    1. Installs Git with winget (built into Windows 10/11) if missing.
    2. Clones this repo (or pulls, if it is already there).
    3. Hands off to scripts\setup_windows.ps1, which installs Python /
       FFmpeg, creates the folders + .venv, and seeds .env.

  Idempotent: safe to re-run.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "$HOME\oloj-homily-automation",
    [string]$RepoUrl = "https://github.com/pivital-az/oloj-homily-automation.git",
    [switch]$SkipSetup
)

$ErrorActionPreference = "Stop"

function Test-Command([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")
}

Write-Host "== OLOJ Homily Automation - bootstrap ==" -ForegroundColor Cyan

# --- 1. Git first (nothing else in this project can come before it) --
if (-not (Test-Command "git")) {
    if (-not (Test-Command "winget")) {
        throw "winget is not available on this machine. Install 'App Installer' from the Microsoft Store, or download Git manually from https://git-scm.com/download/win - then re-run this script."
    }
    Write-Host "Installing Git via winget..."
    winget install --id Git.Git --exact --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "winget failed to install Git (exit $LASTEXITCODE)." }
    Refresh-Path
    if (-not (Test-Command "git")) {
        throw "Git was installed but is not on PATH in this window yet. Close PowerShell, open a new one, and re-run this script - it will pick up where it left off."
    }
}
Write-Host "Git: $(git --version)"

# --- 2. Get the repo --------------------------------------------------
if (Test-Path (Join-Path $InstallDir ".git")) {
    Write-Host "Repo already present at $InstallDir - pulling latest..."
    git -C $InstallDir pull --ff-only
} elseif (Test-Path $InstallDir) {
    throw "$InstallDir exists but is not a git checkout. Move it aside or pass -InstallDir with a different folder."
} else {
    Write-Host "Cloning $RepoUrl -> $InstallDir"
    git clone $RepoUrl $InstallDir
}
Set-Location $InstallDir

# --- 3. Hand off to the full setup ------------------------------------
if ($SkipSetup) {
    Write-Host "Skipping setup (-SkipSetup). Run .\scripts\setup_windows.ps1 when ready."
    exit 0
}
Write-Host "Running the full setup..."
powershell -ExecutionPolicy Bypass -File (Join-Path $InstallDir "scripts\setup_windows.ps1")
if ($LASTEXITCODE -ne 0) { throw "setup_windows.ps1 failed (exit $LASTEXITCODE)." }
