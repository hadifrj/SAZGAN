@echo off
setlocal EnableExtensions
set "SAZGAN_ROOT=%~dp0..\.."
cd /d "%SAZGAN_ROOT%"

@echo off
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
setlocal EnableExtensions
cd /d "%SAZGAN_ROOT%"

echo ============================================================
echo   SAZGAN - Build CLIENT EXE (multi-step first-run wizard)
echo ============================================================
echo.

echo [1/4] Checking Python...
set "PY="
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
    where python >nul 2>&1
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    echo.
    echo [ERROR] Python was not found.
    echo Install Python from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
%PY% --version
echo.

echo [2/4] Installing client build requirements...
%PY% -m pip install -r config\requirements-client.txt
if errorlevel 1 (
    echo.
    echo [ERROR] pip install failed. See the output above for details.
    echo.
    pause
    exit /b 1
)
echo.

echo [3/4] Running PyInstaller...
set "ICON_ARG="
if exist "static\favicon.ico" set "ICON_ARG=--icon static\favicon.ico"
if exist build rmdir /s /q build >nul 2>&1
if exist dist\SazganClient.exe del /q dist\SazganClient.exe >nul 2>&1
%PY% -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name SazganClient ^
  %ICON_ARG% ^
  desktop\client.py
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller failed. See the output above for details.
    echo Common cause: antivirus/Windows Defender blocking PyInstaller
    echo or the generated exe. Try adding an exclusion for this project
    echo folder and run this script again.
    echo.
    pause
    exit /b 1
)
echo.

echo [4/4] Verifying output...
if not exist "dist\SazganClient.exe" (
    echo.
    echo [WARNING] Build reported success but dist\SazganClient.exe was not found.
    echo Check the PyInstaller output above for hidden errors.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Build finished successfully!
echo   Output: dist\SazganClient.exe
echo.
echo   This file contains NO app code and NO database - it only
echo   opens a window pointed at a running Sazgan server (LAN
echo   address or HTTPS domain). Copy it to any Windows PC on the
echo   network and run it; it will ask for the server address once.
echo   To change the server later: SazganClient.exe --setup
echo ============================================================
echo.
pause
