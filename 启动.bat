@echo off
chcp 65001 >nul
title Prompt OS Galgame — Full Stack
cd /d "%~dp0"

echo.
echo ================================================
echo    Prompt OS Galgame Runtime
echo    AI Narrative Engine
echo ================================================
echo.
echo [INFO] 运行日志: %~dp0data\app.log
echo [INFO] 错误日志: %~dp0data\error.log
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

if not exist "data" mkdir data

echo.
echo [INFO] Starting backend  (API)  -^> http://localhost:8000
echo [INFO] Starting frontend (UI)  -^> http://localhost:5173
echo.
echo        Close this window to stop both servers.
echo.

:: ── Start backend (must run in project root for data\*.log) ──
start "PromptOS-Backend" cmd /c "cd /d "%~dp0" && python -m uvicorn ui.web_app:app --host 127.0.0.1 --port 8000"

:: ── Start frontend (Vite 就绪后会自动打开浏览器) ──
cd frontend
call npm run dev
cd ..

:: ── Cleanup on exit ──
taskkill /f /fi "WINDOWTITLE eq PromptOS-Backend*" >nul 2>&1
echo.
echo [INFO] Servers stopped.
pause
