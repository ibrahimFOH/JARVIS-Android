@echo off
cd /d C:\Jarvis\J.A.R.V.I.S
curl.exe -s http://127.0.0.1:11434/api/tags >nul 2>&1
if not %errorlevel%==0 (
    where ollama >nul 2>&1
    if %errorlevel%==0 (
        start "" /min ollama serve
        timeout /t 3 /nobreak >nul
    )
)
start "" "C:\Jarvis\J.A.R.V.I.S\venv\Scripts\pythonw.exe" "C:\Jarvis\J.A.R.V.I.S\main.py"
