@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1
echo Stagepulse JARVIS baslatiliyor...
call run_jarvis.bat %*
exit /b %errorlevel%
