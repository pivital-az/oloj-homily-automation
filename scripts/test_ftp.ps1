<#
.SYNOPSIS
  Test the FTP connection to the recorder, before running the pipeline.

.DESCRIPTION
  Uses the FTP values from .env (override any of them with parameters):
  checks the recorder is reachable, logs in, lists and parses the MP3
  chunks, shows how the latest Sunday groups into services, and with
  -Download also pulls the newest file to verify a real download.

.EXAMPLE
  .\scripts\test_ftp.ps1
  .\scripts\test_ftp.ps1 -Download
  .\scripts\test_ftp.ps1 -FtpHost 10.16.10.232 -FtpUser Admin -FtpPassword ""
#>
[CmdletBinding()]
param(
    [string]$FtpHost,
    [int]$FtpPort,
    [string]$FtpUser,
    [string]$FtpPassword,
    [string]$RemoteDir,
    [switch]$Download
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
# Pick up PATH changes from winget installs made earlier in this session
# (new tools like ffmpeg/git are registered in the registry before they
# appear in this window's PATH).
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment not found. Run .\scripts\setup_windows.ps1 first."
}

$ArgsList = @((Join-Path $RepoRoot "src\test_ftp.py"))
if ($PSBoundParameters.ContainsKey("FtpHost"))     { $ArgsList += @("--host", $FtpHost) }
if ($PSBoundParameters.ContainsKey("FtpPort"))     { $ArgsList += @("--port", $FtpPort) }
if ($PSBoundParameters.ContainsKey("FtpUser"))     { $ArgsList += @("--user", $FtpUser) }
if ($PSBoundParameters.ContainsKey("FtpPassword")) { $ArgsList += @("--password", $FtpPassword) }
if ($PSBoundParameters.ContainsKey("RemoteDir"))   { $ArgsList += @("--remote-dir", $RemoteDir) }
if ($Download)                                     { $ArgsList += "--download" }

& $VenvPython @ArgsList
exit $LASTEXITCODE
