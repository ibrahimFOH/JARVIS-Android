@echo off
setlocal
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
  set "PYTHON=%CD%\venv\Scripts\python.exe"
) else (
  set "PYTHON=py -3"
)
echo Starting JARVIS Android LAN bridge...
start "JARVIS Android Bridge" cmd /k ""%PYTHON%" android_bridge.py"
echo Starting Windows JARVIS desktop...
call run_jarvis.bat
endlocal
