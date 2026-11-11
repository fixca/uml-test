@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\launcher.ps1" -Mode Run
set "APP_EXIT_CODE=%ERRORLEVEL%"
if not "%APP_EXIT_CODE%"=="0" (
    echo.
    echo An error occurred. The console will remain open to show the error.
    pause
    exit /b %APP_EXIT_CODE%
)
rem Success
exit /b 0
