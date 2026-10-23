@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo   J.A.R.V.I.S. // STAGEPULSE EXE BUILDER
echo ==========================================
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" build_jarvis_exe.py
) else (
  py -3 build_jarvis_exe.py
)
if errorlevel 1 (
  echo.
  echo BUILD FAILED. Check the error above.
  pause
  exit /b 1
)
echo.
echo Build output: "%~dp0dist\JARVIS\JARVIS.exe"
echo Copy the whole dist\JARVIS folder, not only JARVIS.exe.
pause
