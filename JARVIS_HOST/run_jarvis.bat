@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1

echo Starting Stagepulse JARVIS...
echo.

if not exist "venv\Scripts\python.exe" (
    echo Virtual environment not found!
    echo Please run install.bat first.
    pause
    exit /b 1
)

call "venv\Scripts\activate.bat"
python main.py %*
set "JARVIS_EXIT_CODE=%errorlevel%"

if not "%JARVIS_EXIT_CODE%"=="0" (
    echo.
    echo JARVIS encountered an error (code %JARVIS_EXIT_CODE%).
    pause
)
exit /b %JARVIS_EXIT_CODE%
