# Script de build pentru toate serviciile MediHelp

Write-Host "Building MediHelp Services..." -ForegroundColor Green

# Build Gateway Service
Write-Host "`nBuilding Gateway Service..." -ForegroundColor Yellow
docker build -t medihelp-gateway:latest ./gateway_service

# Build User Profile Service
Write-Host "`nBuilding User Profile Service..." -ForegroundColor Yellow
docker build -t medihelp-user-profile:db1 ./user_profile_service

# Build Prescription Service
Write-Host "`nBuilding Prescription Service..." -ForegroundColor Yellow
docker build -t medihelp-prescription:latest ./prescription_service

# Build Inventory Service
Write-Host "`nBuilding Inventory Service..." -ForegroundColor Yellow
docker build -t medihelp-inventory:latest ./inventory_service

# Build Pharmacy Service
Write-Host "`nBuilding Pharmacy Service..." -ForegroundColor Yellow
docker build -t medihelp-pharmacy:latest ./pharmacy_service

# Build Frontend
Write-Host "`nBuilding Frontend..." -ForegroundColor Yellow
docker build -t medihelp-frontend:latest ./frontend

Write-Host "`nAll services built successfully!" -ForegroundColor Green
Write-Host "`nTo deploy, run: docker stack deploy -c deployment/stack.yml medihelp" -ForegroundColor Cyan

