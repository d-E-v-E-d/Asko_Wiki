param(
  [string]$Site = "all"
)

$ErrorActionPreference = "Stop"

Write-Host "Nightly Git-Backup ist deaktiviert: sites/review werden nicht zu GitHub synchronisiert."
Write-Host "Gewaehlter Bereich: $Site"
exit 0
