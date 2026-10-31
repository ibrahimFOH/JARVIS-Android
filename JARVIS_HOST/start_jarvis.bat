@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1
curl.exe -s http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
  where ollama >nul 2>&1
  if not errorlevel 1 (
    start "" /min ollama serve
    timeout /t 3 /nobreak >nul
  )
)
if not exist "venv\Scripts\pythonw.exe" (
  echo HATA: Sanal ortam yok. Once install.bat dosyasini calistirin.
  pause
  exit /b 1
)
start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0main.py"
exit /b 0
