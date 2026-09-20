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
echo   SAZGAN - Build LITE CLIENT EXE (no webview / no CEF)
echo   Opens the server in the user's normal default browser.
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

echo [2/4] Installing PyInstaller (only dependency - tkinter/webbrowser are stdlib)...
%PY% -m pip install pyinstaller
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
if exist dist\SazganClientLite.exe del /q dist\SazganClientLite.exe >nul 2>&1
%PY% -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name SazganClientLite ^
  %ICON_ARG% ^
  desktop\client_lite.py
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller failed. See the output above for details.
    echo.
    pause
    exit /b 1
)
echo.

echo [4/4] Verifying output...
if not exist "dist\SazganClientLite.exe" (
    echo.
    echo [WARNING] Build reported success but dist\SazganClientLite.exe was not found.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Build finished successfully!
echo   Output: dist\SazganClientLite.exe
echo.
echo   No webview, no CEF, no WebView2 - works on Windows 7 SP1+.
echo   First run asks for the server address, then opens it in the
echo   user's default web browser. Change server later with:
echo   SazganClientLite.exe --setup
echo ============================================================
echo.
pause
