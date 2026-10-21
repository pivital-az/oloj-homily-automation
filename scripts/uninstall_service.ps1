<#
.SYNOPSIS
  Remove the OLOJ scheduled tasks installed by install_service.ps1.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"
$Names = @(
    "OLOJ Homily Automation - Sunday",
    "OLOJ Homily Automation - Monday catch-up",   # name used by the first version
    "OLOJ Homily Automation - Monday",
    "OLOJ Homily Automation - Logon catch-up"
)
foreach ($Name in $Names) {
    if (Get-ScheduledTask -TaskName $Name -TaskPath "\OLOJ\" -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Name -TaskPath "\OLOJ\" -Confirm:$false
        Write-Host "Removed: \OLOJ\$Name"
    } else {
        Write-Host "Not installed: \OLOJ\$Name"
    }
}
