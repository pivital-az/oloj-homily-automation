<#
.SYNOPSIS
  Download the Whisper models (small + medium) into .\models, and
  optionally pull the local LLM into Ollama.

.EXAMPLE
  .\scripts\install_models.ps1
  .\scripts\install_models.ps1 -IncludeOllamaModel
#>
[CmdletBinding()]
param(
    [switch]$IncludeOllamaModel,
    [string]$OllamaModel = "llama3.1:8b"
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

# Read MODELS_DIR from .env if present, else default .\models
$ModelsDir = ".\models"
$EnvFile = Join-Path $RepoRoot ".env"
if (Test-Path $EnvFile) {
    $Line = Select-String -Path $EnvFile -Pattern "^\s*MODELS_DIR\s*=\s*(.+)$" | Select-Object -First 1
    if ($Line) { $ModelsDir = $Line.Matches[0].Groups[1].Value.Trim() }
}
if (-not [System.IO.Path]::IsPathRooted($ModelsDir)) {
    $ModelsDir = Join-Path $RepoRoot $ModelsDir
}

& $VenvPython (Join-Path $RepoRoot "scripts\install_models.py") --models-dir $ModelsDir
if ($LASTEXITCODE -ne 0) { throw "Model download failed." }

if ($IncludeOllamaModel) {
    if (Get-Command "ollama" -ErrorAction SilentlyContinue) {
        Write-Host "Pulling Ollama model $OllamaModel ..."
        ollama pull $OllamaModel
    } else {
        Write-Warning "Ollama is not installed - skipping LLM model. Re-run setup with -InstallOllama, or ignore this if ENABLE_OLLAMA=false."
    }
}

Write-Host "Models installed in $ModelsDir" -ForegroundColor Green
