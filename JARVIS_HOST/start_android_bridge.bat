@echo off
setlocal
cd /d "%~dp0"
title JARVIS Android Bridge
echo.
echo ==========================================
echo   JARVIS ANDROID BRIDGE
echo ==========================================
echo.
if not exist "android_bridge.py" (
  echo HATA: android_bridge.py bulunamadi.
  pause
  exit /b 1
)
if exist "venv\Scripts\python.exe" (
  set "PYTHON=venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)
echo Bridge baslatiliyor...
echo Tablet ayni Wi-Fi aginda olmali.
echo.
"%PYTHON%" android_bridge.py
pause
