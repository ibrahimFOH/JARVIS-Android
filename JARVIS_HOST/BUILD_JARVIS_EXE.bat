@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1

echo ================================================
echo STAGEPULSE JARVIS - TEK DOSYA EXE DERLEMESI
echo ================================================

where py >nul 2>nul
if errorlevel 1 goto :python_missing
py -3.11 -c "import sys; assert sys.version_info[:2] == (3,11), sys.version" >nul 2>nul
if errorlevel 1 goto :python_missing

rem Kaynak calistiricinin kullandigi venv ile ayni Python ortamini kullan.
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" -c "import sys; assert sys.version_info[:2] == (3,11), sys.version" >nul 2>nul
  if errorlevel 1 rmdir /s /q "venv"
)
if not exist "venv\Scripts\python.exe" (
  py -3.11 -m venv venv
  if errorlevel 1 goto :fail
)

"venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail
"venv\Scripts\python.exe" build_jarvis_exe.py
if errorlevel 1 goto :fail

if not exist "dist\StagepulseJARVIS.exe" goto :fail
for %%F in ("dist\StagepulseJARVIS.exe") do set EXE_BYTES=%%~zF
if not defined EXE_BYTES goto :fail
if %EXE_BYTES% LSS 1000000 goto :fail

echo.
echo BUILD OK: %~dp0dist\StagepulseJARVIS.exe
echo Boyut: %EXE_BYTES% bayt
pause
exit /b 0

:python_missing
echo HATA: Python 3.11 x64 ve Python Launcher gerekli.
echo Python 3.11 x64 kurup yeniden deneyin.
goto :fail

:fail
echo.
echo DERLEME BASARISIZ. Yukaridaki ilk hatayi kontrol edin.
pause
exit /b 1
