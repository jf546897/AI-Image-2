@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Build_Portable_Zip.ps1"
if errorlevel 1 (
    echo.
    echo 便携包构建失败，请查看上面的错误信息。
    pause
    exit /b 1
)

echo.
echo 便携包已生成：dist\AI-image2-portable.zip
endlocal
