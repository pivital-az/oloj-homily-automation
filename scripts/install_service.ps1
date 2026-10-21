<#
.SYNOPSIS
  Install the background automation as Windows Scheduled Tasks.
  (Windows has no cron - Task Scheduler is the equivalent service,
  and it is itself a Windows service that starts automatically at boot.)

.DESCRIPTION
  Creates three tasks under \OLOJ\ , all running the same idempotent
  command:  powershell -File scripts\run_pipeline.ps1  (latest Sunday)

    * "OLOJ Homily Automation - Sunday"        Sundays 19:00 local
    * "OLOJ Homily Automation - Monday"        Mondays 07:00 catch-up
    * "OLOJ Homily Automation - Logon catch-up"  At every logon (+5 min)

  RESTART-PROOFING - why a reboot cannot silently kill this:
    1. Scheduled Tasks are stored on disk and the Task Scheduler
       service auto-starts with Windows. Nothing needs to be "turned
       back on" after a restart - the Sunday/Monday tasks will fire
       at their next scheduled times as usual.
    2. -StartWhenAvailable: if the laptop was OFF (or asleep and could
       not wake) at a scheduled time, the missed run starts as soon
       as the machine is available again, instead of being skipped.
    3. The logon catch-up task covers the remaining hole: laptop was
       off all Sunday evening, someone opens it Tuesday - the pipeline
       runs 5 minutes after logon and processes the latest Sunday.
       The pipeline is idempotent (data\state.json), so extra runs
       skip services that are already completed and cost ~seconds.
    4. Laptop power traps are disabled: the tasks are allowed to start
       on battery and are not stopped if the laptop switches to
       battery, and a failed run is retried 3 times, 10 minutes apart.
    5. -WakeToRun asks Windows to wake the laptop for the Sunday run.

  ONE LIMIT TO KNOW ABOUT: by default the tasks run as the current
  user with an Interactive logon, i.e. a run can only start while
  that user is logged on (which the logon catch-up also guarantees
  will happen right after any sign-in). If this laptop should process
  homilies while sitting at the login screen, either enable Windows
  auto-logon for its parish account, or install with SYSTEM -
  see -RunAsSystem - but note SYSTEM cannot use that user's Dropbox
  sync folder or stored git credentials.

.EXAMPLE
  .\scripts\install_service.ps1
  .\scripts\install_service.ps1 -SundayTime "20:30"
#>
[CmdletBinding()]
param(
    [string]$SundayTime = "19:00",
    [string]$MondayTime = "07:00",
    [switch]$RunAsSystem
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $RepoRoot "scripts\run_pipeline.ps1"

$Action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Runner`"" `
    -WorkingDirectory $RepoRoot

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -DontStopOnIdleEnd `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 10) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 6) `
    -MultipleInstances IgnoreNew

if ($RunAsSystem) {
    $Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
} else {
    $Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
}

$LogonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$LogonTrigger.Delay = "PT5M"

$Description = "Our Lady of Joy: download the latest Sunday's services from the DN-900R, extract + transcribe each homily, publish the blog post to Dropbox and the episode to the podcast RSS/Spotify feed. Idempotent - safe to run extra times."

$Tasks = @(
    @{ Name = "OLOJ Homily Automation - Sunday";        Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At $SundayTime },
    @{ Name = "OLOJ Homily Automation - Monday";        Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $MondayTime },
    @{ Name = "OLOJ Homily Automation - Logon catch-up"; Trigger = $LogonTrigger }
)

foreach ($Task in $Tasks) {
    Register-ScheduledTask -TaskName $Task.Name -TaskPath "\OLOJ\" `
        -Action $Action -Trigger $Task.Trigger -Settings $Settings `
        -Principal $Principal -Description $Description -Force | Out-Null
    Write-Host "Installed scheduled task: \OLOJ\$($Task.Name)"
}

Write-Host ""
Write-Host "Background automation installed and restart-proof:" -ForegroundColor Green
Write-Host "  - Tasks survive reboots (Task Scheduler auto-starts with Windows)."
Write-Host "  - A run missed while the laptop was off fires as soon as it is back (StartWhenAvailable),"
Write-Host "    and again 5 minutes after the next logon (Logon catch-up task)."
Write-Host "  - Check status any time:  Get-ScheduledTask -TaskPath '\OLOJ\' | Get-ScheduledTaskInfo"
Write-Host "  - Remove everything:     .\scripts\uninstall_service.ps1"
