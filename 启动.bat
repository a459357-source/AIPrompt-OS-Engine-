@echo off
chcp 65001 >nul 2>&1
title Galgame Runtime

echo.
echo ================================================
echo    Prompt OS Galgame Runtime v2
echo    Epoch of Starlight
echo ================================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+
    pause
    exit /b 1
)

:: Check API key
if "%DEEPSEEK_API_KEY%"=="" (
    echo [INFO] DEEPSEEK_API_KEY env var not set.
    echo        You can set it via web UI at /settings
    echo        or set environment variable:
    echo        set DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
    echo.
)

:: Install deps
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
echo [INFO] Starting web server...
echo        Open http://localhost:8000
echo        Press Ctrl+C to stop
echo.

cd /d "%~dp0"
python engine/run.py --mode web

pause
