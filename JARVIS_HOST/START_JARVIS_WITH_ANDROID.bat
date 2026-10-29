@echo off
setlocal
cd /d "%~dp0"
echo Starting Stagepulse JARVIS desktop...
echo After startup, use the ANDROID HOST button to enable a secured-token LAN session.
echo Use only trusted private Wi-Fi. Never port-forward TCP 8765 to the internet.
call run_jarvis.bat
endlocal
