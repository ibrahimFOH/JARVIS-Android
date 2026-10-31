@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1
if not exist "venv\Scripts\pythonw.exe" (
  echo HATA: Sanal ortam bulunamadi. Once install.bat dosyasini calistirin.
  pause
  exit /b 1
)
start "" /b "%~dp0venv\Scripts\pythonw.exe" "%~dp0main.py"
exit /b 0
