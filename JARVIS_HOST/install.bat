@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1
echo ================================================
echo   STAGEPULSE JARVIS - KURULUM
echo ================================================

where py >nul 2>nul
if errorlevel 1 goto python_missing
py -3.11 --version >nul 2>nul
if errorlevel 1 goto python_missing

if not exist "venv\Scripts\python.exe" (
  py -3.11 -m venv venv
  if errorlevel 1 goto fail
)

echo [1/4] Python ortami hazirlaniyor...
"venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto fail

echo [2/4] Bagimliliklar yukleniyor...
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail

echo [3/4] Yapilandirma hazirlaniyor...
if not exist "config\config.json" copy "config\config.example.json" "config\config.json" >nul
if not exist "config\config.json" goto fail

echo [4/4] Veri klasorleri olusturuluyor...
if not exist logs mkdir logs
if not exist screenshots mkdir screenshots

echo.
echo KURULUM TAMAMLANDI.
echo JARVIS'i baslatmak icin run_jarvis.bat dosyasini calistirin.
echo Tek dosya EXE icin BUILD_JARVIS_EXE.bat dosyasini calistirin.
pause
exit /b 0

:python_missing
echo HATA: Python 3.11 x64 ve Python Launcher gerekli.
goto fail

:fail
echo.
echo KURULUM BASARISIZ. Onceki hata iletisini kontrol edin.
pause
exit /b 1
