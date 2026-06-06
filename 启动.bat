@echo off
title Prompt OS Galgame

echo.
echo ================================================
echo    Prompt OS Galgame Runtime
echo    AI Narrative Engine
echo ================================================
echo.
echo [Tip] Double-click start.hta for normal launch
echo        This console shows server logs
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+
    pause
    exit /b 1
)

pip show fastapi >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
)

echo.
echo [INFO] Starting server...
echo        Browser will open automatically
echo        Window closes when server stops
echo.

cd /d "%~dp0"
python engine\run.py --mode web
exit /b %errorlevel%
