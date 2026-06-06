@echo off
chcp 65001 >nul 2>&1
title Prompt OS Galgame

echo.
echo ================================================
echo    Prompt OS Galgame Runtime
echo    Epoch of Starlight  ^|  AI 互动叙事引擎
echo ================================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Python，请安装 Python 3.10+
    echo          https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check API key
if "%DEEPSEEK_API_KEY%"=="" (
    echo [INFO] 未设置 DEEPSEEK_API_KEY 环境变量
    echo        启动后可在 Web 设置页面 ^(/settings^) 输入
    echo.
)

:: Install deps
pip show fastapi >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 正在安装依赖...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] 依赖安装失败
        pause
        exit /b 1
    )
)

echo.
echo [INFO] 服务器启动中...
echo        浏览器将自动打开
echo        按 Ctrl+C 停止
echo.
echo 提示：下次可直接双击 "启动.vbs" 静默启动（无命令行窗口）
echo       运行 "安装桌面快捷方式.vbs" 可在桌面创建快捷方式
echo.

cd /d "%~dp0"
python engine/run.py --mode web

pause
