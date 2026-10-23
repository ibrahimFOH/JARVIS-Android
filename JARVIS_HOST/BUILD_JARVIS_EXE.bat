@echo off
setlocal
cd /d "%~dp0"
echo ================================================
echo STAGEPULSE JARVIS - TEK DOSYA EXE DERLEMESI
echo ================================================
where py >nul 2>nul
if errorlevel 1 (
  echo HATA: Python Launcher bulunamadi. Python 3.11 x64 kurun.
  pause
  exit /b 1
)
py -3.11 -c "import sys; assert sys.version_info[:2] == (3,11)" >nul 2>nul
if errorlevel 1 (
  echo HATA: Python 3.11 x64 gerekli.
  pause
  exit /b 1
)
py -3.11 build_jarvis_exe.py
if errorlevel 1 (
  echo.
  echo DERLEME BASARISIZ. Yukaridaki hata mesajlarini kontrol edin.
  pause
  exit /b 1
)
echo.
echo Tek dosya EXE: %~dp0dist\StagepulseJARVIS.exe
pause
