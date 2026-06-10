param(
  [switch]$NoClean,
  [switch]$Serve,
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

# Repo-Root als Basis (damit Pfade immer stimmen, egal von wo man startet)
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$portalCfg = "portal\mkdocs.yml"
$python = "C:\Users\Transalpina\AppData\Local\Programs\Python\Python310\python.exe"
$areas = Get-ChildItem -Path "sites" -Directory |
  Where-Object { Test-Path (Join-Path $_.FullName "mkdocs.yml") } |
  Select-Object -ExpandProperty Name

function Invoke-MkDocsBuild([string]$ConfigPath) {
  $mkdocsCmd = Get-Command mkdocs -ErrorAction SilentlyContinue
  if ($mkdocsCmd) {
    & $mkdocsCmd.Source build -f $ConfigPath
    return
  }

  if (-not (Test-Path $python)) {
    throw "Weder 'mkdocs' noch Python gefunden. Erwartet: $python"
  }

  & $python -m mkdocs build -f $ConfigPath
}

Write-Host "== Build All ==" -ForegroundColor Cyan
Write-Host "RepoRoot: $RepoRoot" -ForegroundColor DarkGray

if (-not (Test-Path $portalCfg)) {
  throw "Portal config not found: $portalCfg"
}

if (-not $NoClean) {
  Write-Host "Cleaning ./site ..." -ForegroundColor Yellow
  Remove-Item -Recurse -Force "site" -ErrorAction SilentlyContinue
}

# --- Portal ---
Write-Host "Building portal -> /" -ForegroundColor Green
Invoke-MkDocsBuild $portalCfg

# --- Areas ---
foreach ($a in $areas) {
  $cfg = "sites\$a\mkdocs.yml"
  $route = $a.ToLowerInvariant()
  if (Test-Path $cfg) {
    Write-Host "Building $a -> /$route/" -ForegroundColor Green
    Invoke-MkDocsBuild $cfg
  } else {
    Write-Host "Skip $a (no mkdocs.yml): $cfg" -ForegroundColor Yellow
  }
}

Write-Host "Build completed." -ForegroundColor Cyan

if ($Serve) {
  Write-Host "Serving ./site on http://127.0.0.1:$Port/" -ForegroundColor Cyan
  if (-not (Test-Path $python)) {
    throw "Python nicht gefunden: $python"
  }
  & $python -m http.server $Port -d site
}
