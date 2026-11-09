<#
.SYNOPSIS
  Launch the OLOJ homily desktop GUI.

.DESCRIPTION
  Runs src\gui.py with the repo virtualenv's Python (tkinter ships
  with Python, so nothing else needs installing). The GUI builds and
  runs the same scripts\run_pipeline.ps1 command a person would type,
  and shows its output live.

  The GUI is launched with pythonw.exe - the windowed Python - NOT
  python.exe. python.exe is a console program: Windows attaches a
  black terminal window to it that stays open for the GUI's whole
  life, and closing that terminal kills the GUI with it. pythonw.exe
  is the same interpreter without the console, so the GUI stands on
  its own. Start-Process detaches it, and this script then exits, so
  the PowerShell window behind the launch does not linger either.

  For a one-click launch, run .\scripts\install_desktop_shortcut.ps1
  once - it puts an "OLOJ Homily Automation" shortcut on the desktop
  that calls this script (with the launcher's window hidden).

.EXAMPLE
  .\scripts\run_gui.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$GuiPy = Join-Path $RepoRoot "src\gui.py"
$VenvPythonW = Join-Path $RepoRoot ".venv\Scripts\pythonw.exe"
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPythonW) {
    Start-Process -FilePath $VenvPythonW -ArgumentList "`"$GuiPy`"" `
        -WorkingDirectory $RepoRoot
} elseif (Test-Path $VenvPython) {
    # A venv without pythonw.exe should not exist on Windows, but
    # fall back to the console interpreter rather than not launching.
    Write-Warning "pythonw.exe not found in the venv - launching with python.exe, which keeps a console window open."
    & $VenvPython $GuiPy
} else {
    throw "Virtual environment not found. Run .\scripts\setup_windows.ps1 first."
}
