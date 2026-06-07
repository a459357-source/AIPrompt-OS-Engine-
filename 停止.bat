@echo off
title PromptOS Stop
cd /d "%~dp0"
echo Checking ports 8000 and 5173...
python scripts\stop_servers.py
echo.
echo If ports are idle, run start.bat or start-standalone.bat
echo.
pause
