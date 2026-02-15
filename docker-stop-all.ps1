# Останавливает все Docker-контейнеры (Plane + любые другие)
# Usage: .\docker-stop-all.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Set-Location $ProjectRoot

Write-Host "Stopping Plane stack (docker-compose-local.yml)..." -ForegroundColor Yellow
docker compose -f docker-compose-local.yml down --remove-orphans
if ($LASTEXITCODE -ne 0) {
    Write-Host "Compose down failed (no stack running?)." -ForegroundColor Yellow
}

Write-Host "`nStopping all remaining running containers..." -ForegroundColor Yellow
$ids = @(docker ps -q)
if ($ids.Count -gt 0) {
    docker stop $ids
    Write-Host "Stopped $($ids.Count) container(s)." -ForegroundColor Green
} else {
    Write-Host "No running containers." -ForegroundColor Gray
}

Write-Host "`nDone. All Docker containers stopped." -ForegroundColor Green
