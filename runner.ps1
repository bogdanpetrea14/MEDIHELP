Write-Host "==> Setez directorul de lucru la folderul scriptului..." -ForegroundColor Cyan
Set-Location $PSScriptRoot

Write-Host "==> Verific Docker Swarm..." -ForegroundColor Cyan
$dockerInfo = docker info 2>$null

if ($dockerInfo -match "Swarm: active") {
    Write-Host "   Swarm este deja activ." -ForegroundColor Green
} else {
    Write-Host "   Swarm nu este activ. Pornesc 'docker swarm init'..." -ForegroundColor Yellow
    docker swarm init
}

Write-Host "==> Build imagini Docker..." -ForegroundColor Cyan

Write-Host "   - medihelp-user-profile:db1" -ForegroundColor Yellow
docker build -t medihelp-user-profile:db1 .\user_profile_service

Write-Host "   - medihelp-gateway" -ForegroundColor Yellow
docker build -t medihelp-gateway .\gateway_service

Write-Host "   - medihelp-frontend" -ForegroundColor Yellow
docker build -t medihelp-frontend .\frontend

Write-Host "   - medihelp-prescription" -ForegroundColor Yellow
docker build -t medihelp-prescription .\prescription_service

Write-Host "   - medihelp-inventory" -ForegroundColor Yellow
docker build -t medihelp-inventory .\inventory_service

Write-Host "==> Deploy Docker stack 'medihelp'..." -ForegroundColor Cyan
docker stack deploy -c .\deployment\stack.yml medihelp

Write-Host "==> Servicii în stack-ul 'medihelp':" -ForegroundColor Cyan
docker service ls

Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "   Proiectul MediHelp rulează acum." -ForegroundColor Green
Write-Host ""
Write-Host "   Frontend:   http://localhost:8082" -ForegroundColor White
Write-Host "   Gateway:    http://localhost:8080/health" -ForegroundColor White
Write-Host "   Keycloak:   http://localhost:8081" -ForegroundColor White
Write-Host "=======================================" -ForegroundColor Cyan
