@echo off
setlocal

if "%1"=="" (
    echo Usage: run.bat [run^|test]
    exit /b 1
)

if /I "%1"=="run" (
    cd /d "%~dp0"
    python -m src.main
    exit /b %errorlevel%
)

if /I "%1"=="test" (
    cd /d "%~dp0"
    python -m unittest discover -s tests
    exit /b %errorlevel%
)

echo Invalid option: %1
echo Usage: run.bat [run^|test]
exit /b 1
