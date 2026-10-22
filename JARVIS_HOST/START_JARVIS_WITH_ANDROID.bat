@echo off
setlocal
cd /d "%~dp0"
echo Starting Windows JARVIS with authenticated Android LAN bridge...
echo The bridge starts inside the desktop app. Keep JARVIS running while using Android.
call run_jarvis.bat
endlocal
