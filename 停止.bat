@echo off
chcp 65001 >nul
title PromptOS — 停止服务
cd /d "%~dp0"
echo 正在停止占用 8000 / 5173 端口的进程...
python scripts\stop_servers.py
echo.
pause
