# Script pentru rularea testelor unitare
# Rulează testele pentru funcționalitățile avansate (Redis Caching, Rate Limiting, Replicare)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Running Advanced Features Tests" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verifică dacă directorul tests există
if (-not (Test-Path "tests\test_advanced_features.py")) {
    Write-Host "ERROR: Nu s-a găsit fișierul de test: tests\test_advanced_features.py" -ForegroundColor Red
    exit 1
}

Write-Host "Rulând testele într-un container Docker..." -ForegroundColor Yellow
Write-Host ""

# Rulează testele într-un container Python temporar
docker run --rm -v "${PWD}\tests:/tests" python:3.11-slim python -m unittest discover -s /tests -p test_*.py -v

$exitCode = $LASTEXITCODE

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Toate testele au trecut cu succes!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  Unele teste au eșuat!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
}

exit $exitCode
