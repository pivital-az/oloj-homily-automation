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

  MICROSOFT STORE PYTHON STUB: Windows pre-installs fake python.exe /
  py.exe "app execution aliases" under %LOCALAPPDATA%\Microsoft\
  WindowsApps. They are NOT Python - running one just prints "Python
  was not found; run without arguments to install from the Microsoft
  Store". An early version of this script treated that stub as a real
  Python, skipped the install, and then failed creating the venv.
  Get-RealPython below ignores anything under WindowsApps and verifies
  candidates by actually running --version.
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

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")
}

function Install-WingetPackage([string]$Id, [string]$DisplayName, [switch]$RetryAfterUninstall) {
    if (-not (Test-Command "winget")) {
        throw "winget is not available. Install 'App Installer' from the Microsoft Store, or install $DisplayName manually, then re-run."
    }
    Write-Host "Installing $DisplayName ($Id) via winget..."
    winget install --id $Id --exact --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0 -and $RetryAfterUninstall) {
        # Installer exit 1603 most often means a partial/broken earlier
        # install is registered. Remove whatever winget knows about,
        # then retry once with --force.
        Write-Warning "$DisplayName install failed (exit $LASTEXITCODE) - removing any partial install and retrying with --force..."
        winget uninstall --id $Id --exact --silent 2>$null | Out-Null
        winget install --id $Id --exact --silent --force --accept-package-agreements --accept-source-agreements
    }
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed to install $DisplayName (exit $LASTEXITCODE). See docs\TROUBLESHOOTING.md - for Python, a reboot plus removing leftover Python entries in Settings > Apps usually clears installer error 1603."
    }
    Refresh-Path
}

function Get-RealPython {
    # Returns the path of a REAL python.exe, or $null. Skips the
    # Microsoft Store execution-alias stubs in WindowsApps and verifies
    # every candidate by running it.
    $Candidates = @()

    # 1. Standard install locations (per-user and machine-wide).
    $Roots = @(
        "$env:LOCALAPPDATA\Programs\Python",
        "$env:ProgramFiles",
        "${env:ProgramFiles(x86)}",
        "C:\"
    )
    foreach ($Root in $Roots) {
        if ($Root -and (Test-Path $Root)) {
            Get-ChildItem -Path $Root -Directory -Filter "Python3*" -ErrorAction SilentlyContinue |
                ForEach-Object { $Candidates += (Join-Path $_.FullName "python.exe") }
        }
    }

    # 2. Anything on PATH that is not a Store stub.
    foreach ($Cmd in (Get-Command "python.exe" -All -ErrorAction SilentlyContinue)) {
        if ($Cmd.Source -notlike "*\Microsoft\WindowsApps\*") { $Candidates += $Cmd.Source }
    }
    foreach ($Cmd in (Get-Command "py.exe" -All -ErrorAction SilentlyContinue)) {
        # The py launcher: resolve the interpreter it would run.
        if ($Cmd.Source -notlike "*\Microsoft\WindowsApps\*") {
            $Resolved = & $Cmd.Source "-$PythonVersion" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $Resolved -and (Test-Path $Resolved)) { $Candidates += $Resolved }
        }
    }

    foreach ($Candidate in ($Candidates | Select-Object -Unique)) {
        if (-not (Test-Path $Candidate)) { continue }
        $Version = & $Candidate --version 2>$null
        if ($LASTEXITCODE -eq 0 -and $Version -match "^Python 3\.") { return $Candidate }
    }
    return $null
}

Write-Host "== OLOJ Homily Automation - Windows setup ==" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"

# --- 1. Tools ---------------------------------------------------------
if (-not (Test-Command "git"))    { Install-WingetPackage "Git.Git" "Git" }
else { Write-Host "Git: found" }

$Python = Get-RealPython
if (-not $Python) {
    Install-WingetPackage "Python.Python.3.12" "Python 3.12" -RetryAfterUninstall
    $Python = Get-RealPython
}
if (-not $Python) {
    throw @"
Real Python was not found (only the Microsoft Store stub, or nothing).

Try, in order:
  1. Close this PowerShell window, open a NEW one, and re-run this script.
  2. If it still fails: Settings > Apps > Advanced app settings >
     App execution aliases - turn OFF python.exe and python3.exe,
     then install Python from https://www.python.org/downloads/
     (tick 'Add python.exe to PATH'), and re-run this script.
"@
}
Write-Host "Python: $Python ($(& $Python --version))"

if (-not (Test-Command "ffmpeg")) { Install-WingetPackage "Gyan.FFmpeg" "FFmpeg" }
else { Write-Host "FFmpeg: found" }
Refresh-Path
if (-not (Test-Command "ffmpeg")) {
    Write-Warning "ffmpeg is installed but not on PATH in this window yet - it will be in any new PowerShell window and in the scheduled tasks. If you run the pipeline from THIS window, reopen it first."
}

if ($InstallOllama -and -not (Test-Command "ollama")) {
    Install-WingetPackage "Ollama.Ollama" "Ollama"
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
$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    if (Test-Path $VenvDir) {
        Write-Host "Removing incomplete .venv from a previous attempt..."
        Remove-Item -Recurse -Force $VenvDir
    }
    Write-Host "Creating virtual environment (.venv)..."
    & $Python -m venv $VenvDir
    if (-not (Test-Path $VenvPython)) {
        throw "Virtual environment creation failed - $VenvPython was not created. Re-run this script in a NEW PowerShell window; if it still fails, run '$Python -m venv .venv' by hand and note the error."
    }
}
Write-Host "Virtual environment: $VenvPython ($(& $VenvPython --version))"

Write-Host "Installing Python packages from requirements.txt..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip self-upgrade failed." }
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
Write-Host "  2. Test the FTP link:    .\scripts\test_ftp.ps1 -Download"
Write-Host "  3. Download the models:  .\scripts\install_models.ps1"
Write-Host "  4. Dry run:              .\scripts\run_pipeline.ps1 -DryRun"
Write-Host "  5. Install automation:   .\scripts\install_service.ps1"
