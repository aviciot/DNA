@echo off
echo ========================================
echo DNA ISO Certification Dashboard
echo ========================================
echo.

echo Checking Docker...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not installed or not running
    echo Please install Docker Desktop from https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

echo Docker is running!
echo.

echo Starting DNA services...
echo.

cd /d "%~dp0"

docker-compose up -d

echo.
echo ========================================
echo Services are starting up...
echo ========================================
echo.
echo Please wait 30-60 seconds for initialization
echo.
echo URLs:
echo   Frontend:  http://localhost:3003
echo   Backend:   http://localhost:8400
echo   Auth API:  http://localhost:8401
echo.
echo Default Login:
echo   Email:     admin@dna.local
echo   Password:  admin123
echo.
echo To view logs:  docker-compose logs -f
echo To stop:       docker-compose down
echo.
echo ========================================

pause
