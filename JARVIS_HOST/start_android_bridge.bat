@echo off
setlocal
cd /d "%~dp0"
title JARVIS Android Bridge

REM Request administrator rights once so Windows Firewall can accept tablet traffic.
net session >nul 2>&1
if not "%errorlevel%"=="0" (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo.
echo ==========================================
echo   JARVIS ANDROID BRIDGE
echo ==========================================
echo.

netsh advfirewall firewall add rule name="JARVIS Android Bridge 8765" dir=in action=allow protocol=TCP localport=8765 profile=private >nul 2>&1

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
echo Tablet ve Windows ayni Wi-Fi aginda olmali.
echo Port: 8765
echo.

"%PYTHON%" android_bridge.py
pause
