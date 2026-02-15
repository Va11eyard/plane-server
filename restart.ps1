# Plane - full restart: Docker, migrations, build packages + web
# Usage: .\restart.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "Plane: full restart (Docker + migrations + build)..." -ForegroundColor Cyan
Set-Location $ProjectRoot

# 1. Restart Docker (API code is mounted, restart picks up Python changes)
Write-Host "`n[1/4] Restarting Docker containers..." -ForegroundColor Yellow
docker compose -f docker-compose-local.yml restart
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker restart failed." -ForegroundColor Red
    exit 1
}
Write-Host "Docker containers restarted." -ForegroundColor Green

# 2. Migrations
Write-Host "`n[2/4] Waiting 5s, then running migrations..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
docker compose -f docker-compose-local.yml run --rm migrator
if ($LASTEXITCODE -ne 0) {
    Write-Host "Migrations failed (optional)." -ForegroundColor Yellow
} else {
    Write-Host "Migrations done." -ForegroundColor Green
}

# 3. Build packages and web (so i18n, constants, new pages are used)
Write-Host "`n[3/4] Building packages and web..." -ForegroundColor Yellow
pnpm turbo run build --filter=web...
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed - try: pnpm install then run again." -ForegroundColor Yellow
} else {
    Write-Host "Build done." -ForegroundColor Green
}

# 4. Done
Write-Host "`n[4/4] Done." -ForegroundColor Green
Write-Host "`nStart the web app:" -ForegroundColor Cyan
Write-Host "  pnpm --filter=web dev" -ForegroundColor White
Write-Host "`nOpen http://127.0.0.1:3000 and press Ctrl+Shift+R (hard refresh)" -ForegroundColor Cyan
