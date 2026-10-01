@echo off
setlocal
cd /d "%~dp0.."
if exist venv\Scripts\python.exe (
  venv\Scripts\python.exe android_bridge.py
) else (
  py -3 android_bridge.py
)
endlocal
