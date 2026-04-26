@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

title AI Image 2 Portable Launcher
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"

if errorlevel 1 (
    echo.
    echo Launch failed. Please screenshot this window.
    pause
)
endlocal
