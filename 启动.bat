@echo off
title Prompt OS Galgame — Full Stack
cd /d "%~dp0"

echo.
echo ================================================
echo    Prompt OS Galgame Runtime
echo    AI Narrative Engine
echo ================================================
echo.

:: ── Check Python ──
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+
    pause
    exit /b 1
)

:: ── Check Node.js ──
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Install Node.js 18+
    pause
    exit /b 1
)

:: ── Install Python deps if needed ──
pip show fastapi >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing Python dependencies...
    pip install -r requirements.txt
)

:: ── Install frontend deps if needed ──
if not exist "frontend\node_modules" (
    echo [INFO] Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

echo.
echo [INFO] Starting backend  (API)  → http://localhost:8000
echo [INFO] Starting frontend (UI)   → http://localhost:5173
echo.
echo        Close this window to stop both servers.
echo.

:: ── Start backend in background ──
start "PromptOS-Backend" cmd /c "python -m uvicorn ui.web_app:app --host 0.0.0.0 --port 8000"

:: ── Start frontend ──
cd frontend
call npm run dev
cd ..

:: ── Cleanup on exit ──
taskkill /f /fi "WINDOWTITLE eq PromptOS-Backend*" >nul 2>&1
echo.
echo [INFO] Servers stopped.
pause
