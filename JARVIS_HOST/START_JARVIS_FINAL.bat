@echo off
cd /d C:\Jarvis\J.A.R.V.I.S
set "OLLAMA=C:\Users\ECE\AppData\Local\Programs\Ollama\ollama.exe"
if exist "%OLLAMA%" tasklist /FI "IMAGENAME eq ollama.exe" | find /I "ollama.exe" >nul || start "" "%OLLAMA%"
timeout /t 1 /nobreak >nul
"C:\Jarvis\J.A.R.V.I.S\venv\Scripts\python.exe" main.py
