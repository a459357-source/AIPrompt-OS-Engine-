@echo off
chcp 65001 >nul 2>&1
title Prompt OS Galgame

echo.
echo ================================================
echo    Prompt OS Galgame Runtime
echo    AI 互动叙事引擎
echo ================================================
echo.
echo 提示：普通用户请直接双击 "开始游戏.hta"
echo       当前为开发者调试模式（可见日志）
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+
    pause
    exit /b 1
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
echo [INFO] Starting server...
echo        Browser will open automatically
echo        Press Ctrl+C to stop
echo.

cd /d "%~dp0"
python engine/run.py --mode web

pause
