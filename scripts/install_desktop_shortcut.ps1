<#
.SYNOPSIS
  Put an "OLOJ Homily Automation" shortcut on the Windows desktop.

.DESCRIPTION
  The shortcut launches scripts\run_gui.ps1 (the desktop GUI) in a
  normal PowerShell window, with the repo as its working directory.
  It is per-user: it goes on the current user's desktop, so it works
  for the AudioVisual account the pipeline runs as, without needing
  administrator rights or a reboot/logoff. Run it once; re-running
  it just replaces the shortcut with a fresh identical one. The
  shortcut uses assets\oloj-icon.ico (gold microphone in a
  stained-glass arch); if that file is missing the shortcut still
  works, just with the default PowerShell icon.

  This does NOT change the scheduled tasks - Sundays at 19:00 keep
  running unattended. The GUI is for hand runs: a backfill, a retry,
  or a single date with Force.

.EXAMPLE
  .\scripts\install_desktop_shortcut.ps1
#>
[CmdletBinding()]
param(
    [string]$Name = "OLOJ Homily Automation"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $RepoRoot "scripts\run_gui.ps1"
$Desktop = [Environment]::GetFolderPath("Desktop")
$LinkPath = Join-Path $Desktop "$Name.lnk"

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($LinkPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`""
$Shortcut.WorkingDirectory = $RepoRoot
$Shortcut.Description = "Our Lady of Joy homily automation - pick a date or date range and convert it."
$IconPath = Join-Path $RepoRoot "assets\oloj-icon.ico"
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = $IconPath
} else {
    Write-Warning "Icon not found at $IconPath - shortcut will use the default icon."
}
$Shortcut.Save()

Write-Host "Desktop shortcut created: $LinkPath" -ForegroundColor Green
Write-Host "Double-click it to open the GUI. Sundays at 19:00 still run unattended via Task Scheduler."
