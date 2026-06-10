param(
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 8010,
  [switch]$Reload
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$env:APP_ROOT = $RepoRoot
$env:ASKO_LOCAL_NO_GIT = "1"

$siteDir = Join-Path $RepoRoot "site"
if (-not (Test-Path $siteDir)) {
  New-Item -ItemType Directory -Path $siteDir | Out-Null
}

$python = "C:\Users\Transalpina\AppData\Local\Programs\Python\Python310\python.exe"
if (-not (Test-Path $python)) {
  throw "Python nicht gefunden: $python"
}

$args = @("-m", "uvicorn", "app.main:app", "--host", $BindHost, "--port", "$Port")
if ($Reload) {
  $args += @(
    "--reload",
    "--reload-dir", (Join-Path $RepoRoot "app"),
    "--reload-dir", (Join-Path $RepoRoot "sites"),
    "--reload-dir", (Join-Path $RepoRoot "portal"),
    "--reload-dir", (Join-Path $RepoRoot "tools")
  )
}

Write-Host "APP_ROOT=$env:APP_ROOT" -ForegroundColor DarkGray
Write-Host "Starte FastAPI auf http://${BindHost}:${Port}/" -ForegroundColor Cyan
& $python @args
