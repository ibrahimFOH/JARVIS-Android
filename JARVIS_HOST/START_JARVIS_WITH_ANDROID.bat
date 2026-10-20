@echo off
setlocal
cd /d "%~dp0"
echo Starting JARVIS Android LAN bridge...
if exist "venv\Scripts\python.exe" (
  start "JARVIS Android Bridge" cmd /k ""%CD%\venv\Scripts\python.exe" android_bridge.py"
) else (
  start "JARVIS Android Bridge" cmd /k "py -3 android_bridge.py"
)
echo Starting Windows JARVIS desktop...
call run_jarvis.bat
endlocal
