@echo off
chcp 65001 >nul
title PromptOS
cd /d "%~dp0PromptOS"

echo.
echo PromptOS 启动中...
echo  运行日志: %cd%\data\app.log
echo  错误日志: %cd%\data\error.log
echo  关闭 PromptOS 窗口即停止服务
echo.

start "" "PromptOS.exe"
