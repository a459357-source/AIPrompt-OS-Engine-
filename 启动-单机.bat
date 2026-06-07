@echo off
chcp 65001 >nul
title PromptOS
cd /d "%~dp0"

echo.
echo ================================================
echo    PromptOS 单机模式 (内置前端 :8000)
echo ================================================
echo.
echo [INFO] 运行日志: %~dp0data\app.log
echo [INFO] 错误日志: %~dp0data\error.log
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

if not exist "frontend\dist\index.html" (
    echo [INFO] 首次运行，正在构建前端...
    cd frontend
    call npm install
    call npm run build
    cd ..
)

if not exist "data" mkdir data

python launcher.py
pause
