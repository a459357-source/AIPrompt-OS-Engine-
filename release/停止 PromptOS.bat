@echo off
chcp 65001 >nul
title PromptOS Stop
cd /d "%~dp0"

echo.
echo 正在检查 8000 端口（PromptOS 默认端口）...
set KILLED=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
  echo 结束进程 PID %%a ...
  taskkill /F /PID %%a >nul 2>&1
  if not errorlevel 1 set KILLED=1
)

if "%KILLED%"=="1" (
  echo.
  echo 已释放 8000 端口，可重新运行「启动 PromptOS.bat」或 PromptOS.exe
) else (
  echo.
  echo 未发现占用 8000 端口的进程；若程序仍在运行，请直接关闭 PromptOS.exe 黑色窗口
)
echo.
pause
