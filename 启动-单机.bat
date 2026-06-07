@echo off
title PromptOS Standalone
cd /d "%~dp0"

echo.
echo ================================================
echo    PromptOS Standalone (UI on :8000)
echo ================================================
echo.
echo [INFO] Log: %~dp0data\app.log
echo [INFO] Errors: %~dp0data\error.log
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+
    pause
    exit /b 1
)

python scripts\port_guard.py 8000
if %errorlevel% neq 0 (
    pause
    exit /b 1
)

if not exist "frontend\dist\index.html" (
    echo [INFO] First run: building frontend...
    node --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Node.js required to build frontend
        pause
        exit /b 1
    )
    cd frontend
    call npm install
    call npm run build
    cd ..
    if not exist "frontend\dist\index.html" (
        echo [ERROR] Frontend build failed. See npm output above.
        pause
        exit /b 1
    )
)

if not exist "data" mkdir data

python launcher.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Start failed. See data\error.log
)
pause
