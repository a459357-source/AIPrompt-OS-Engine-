@echo off
title PromptOS Galgame Full Stack
cd /d "%~dp0"

echo.
echo ================================================
echo    Prompt OS Galgame Runtime
echo    AI Narrative Engine
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

node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Install Node.js 18+
    pause
    exit /b 1
)

pip show fastapi >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing Python dependencies...
    pip install -r requirements.txt
)

if not exist "frontend\node_modules" (
    echo [INFO] Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

if not exist "data" mkdir data

python scripts\port_guard.py 8000
if %errorlevel% neq 0 (
    pause
    exit /b 1
)
python scripts\port_guard.py 5173
if %errorlevel% neq 0 (
    pause
    exit /b 1
)

echo.
echo [INFO] Backend  API -^> http://127.0.0.1:8000
echo [INFO] Frontend UI -^> http://127.0.0.1:5173
echo        If port in use, run stop.bat first
echo.
echo        Close this window to stop frontend; backend runs in another window
echo.

start "PromptOS Backend" cmd /k "cd /d ""%~dp0"" && python -m uvicorn ui.web_app:app --host 127.0.0.1 --port 8000"

ping 127.0.0.1 -n 3 >nul

cd frontend
call npm run dev
cd ..

taskkill /f /fi "WINDOWTITLE eq PromptOS Backend*" >nul 2>&1
echo.
echo [INFO] Servers stopped.
pause
