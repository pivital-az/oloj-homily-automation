<#
.SYNOPSIS
  Launch the OLOJ homily desktop GUI.

.DESCRIPTION
  Runs src\gui.py with the repo virtualenv's Python (tkinter ships
  with Python, so nothing else needs installing). The GUI builds and
  runs the same scripts\run_pipeline.ps1 command a person would type,
  and shows its output live.

  For a one-click launch, run .\scripts\install_desktop_shortcut.ps1
  once - it puts an "OLOJ Homily Automation" shortcut on the desktop
  that calls this script.

.EXAMPLE
  .\scripts\run_gui.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment not found. Run .\scripts\setup_windows.ps1 first."
}

& $VenvPython (Join-Path $RepoRoot "src\gui.py")
