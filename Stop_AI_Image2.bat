@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

title Stop AI Image 2
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1"

echo.
pause
endlocal
