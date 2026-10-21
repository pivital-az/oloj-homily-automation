<#
.SYNOPSIS
  One-time Windows setup for Our Lady of Joy homily automation.

.DESCRIPTION
  - Installs Git, Python 3.12, FFmpeg (and optionally Ollama) via winget
    when they are missing. Already-installed tools are left alone.
  - Creates the data folder layout, including the models folder.
  - Creates a Python virtual environment in .venv and installs
    requirements.txt into it.
  - Copies .env.example to .env if .env does not exist yet.

  Run from the repo root in PowerShell:
    powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
  Add -InstallOllama if you want the optional local LLM.

.NOTES
  Idempotent: safe to re-run. No administrator rights are required for
  the folder/venv steps; winget may prompt for elevation per package.
#>
[CmdletBinding()]
param(
    [switch]$InstallOllama,
    [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Test-Command([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Install-WingetPackage([string]$Id, [string]$DisplayName) {
    if (-not (Test-Command "winget")) {
        throw "winget is not available. Install 'App Installer' from the Microsoft Store, or install $DisplayName manually, then re-run."
    }
    Write-Host "Installing $DisplayName ($Id) via winget..."
    winget install --id $Id --exact --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed to install $DisplayName (exit $LASTEXITCODE)."
    }
    # Refresh PATH for this session so later checks can see the new tool.
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")
}

Write-Host "== OLOJ Homily Automation - Windows setup ==" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"

# --- 1. Tools ---------------------------------------------------------
if (-not (Test-Command "git"))    { Install-WingetPackage "Git.Git" "Git" }
else { Write-Host "Git: found" }

if (-not (Test-Command "py") -and -not (Test-Command "python")) {
    Install-WingetPackage "Python.Python.3.12" "Python 3.12"
} else { Write-Host "Python: found" }

if (-not (Test-Command "ffmpeg")) { Install-WingetPackage "Gyan.FFmpeg" "FFmpeg" }
else { Write-Host "FFmpeg: found" }

if ($InstallOllama -and -not (Test-Command "ollama")) {
    Install-WingetPackage "Ollama.Ollama" "Ollama"
}

# Prefer the Python launcher; fall back to python.exe on PATH.
$UsePyLauncher = Test-Command "py"
if (-not $UsePyLauncher -and -not (Test-Command "python")) {
    throw "Python was not found after install. Open a new PowerShell window and re-run this script."
}

# --- 2. Folders (including the models folder) ------------------------
$Folders = @("models", "work", "review", "logs", "data", "assets")
foreach ($Folder in $Folders) {
    $Path = Join-Path $RepoRoot $Folder
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
        Write-Host "Created folder: $Folder"
    }
}
# Model sub-folders the installer downloads into.
foreach ($ModelDir in @("faster-whisper-small", "faster-whisper-medium")) {
    $Path = Join-Path $RepoRoot (Join-Path "models" $ModelDir)
    if (-not (Test-Path $Path)) { New-Item -ItemType Directory -Path $Path | Out-Null }
}

# --- 3. Virtual environment + Python packages -----------------------
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment (.venv)..."
    if ($UsePyLauncher) { & py "-$PythonVersion" -m venv (Join-Path $RepoRoot ".venv") }
    else { & python -m venv (Join-Path $RepoRoot ".venv") }
}
Write-Host "Installing Python packages from requirements.txt..."
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $RepoRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install failed." }

# --- 4. .env ----------------------------------------------------------
$EnvFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $RepoRoot ".env.example") $EnvFile
    Write-Host "Created .env from .env.example - EDIT IT before running the pipeline." -ForegroundColor Yellow
} else {
    Write-Host ".env already exists - leaving it alone."
}

Write-Host ""
Write-Host "Setup complete. Next steps:" -ForegroundColor Green
Write-Host "  1. Edit .env  (FTP address/user/password, DROPBOX_HOMILY_DIR)"
Write-Host "  2. Download the models:  .\scripts\install_models.ps1"
Write-Host "  3. Dry run:              .\scripts\run_pipeline.ps1 -DryRun"
Write-Host "  4. Install automation:   .\scripts\install_service.ps1"
