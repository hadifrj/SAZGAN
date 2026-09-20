@echo off
setlocal EnableExtensions
set "SAZGAN_ROOT=%~dp0..\.."
cd /d "%SAZGAN_ROOT%"
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo ============================================================
echo   SAZGAN - Build NATIVE CLIENT EXE (Fast startup)
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
    echo [ERROR] Python was not found.
    pause
    exit /b 1
)
%PY% --version

echo.
echo [2/4] Installing requirements...
%PY% -m pip install -r native_client\requirements-native.txt
if errorlevel 1 goto FAIL

echo.
echo [3/4] Building fast-startup application folder...
if exist build rmdir /s /q build >nul 2>&1
if exist dist\SazganNative rmdir /s /q dist\SazganNative >nul 2>&1
%PY% -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onedir ^
  --windowed ^
  --name SazganNative ^
  --icon "static\icons\sazgan-app.ico" ^
  --add-data "native_client\assets\fonts;native_client\assets\fonts" ^
  --add-data "static\icons;static\icons" ^
  native_client\main.py
if errorlevel 1 goto FAIL

echo.
echo [4/4] Verifying output...
if not exist "dist\SazganNative\SazganNative.exe" goto FAIL

echo.
echo ============================================================
echo   Build finished successfully!
echo   Output: dist\SazganNative\SazganNative.exe
echo   NOTE: onedir is intentional for fast startup; do not convert
 echo   this build back to --onefile unless portability is required.
echo ============================================================
echo.
pause
exit /b 0

:FAIL
echo.
echo [ERROR] Native Client build failed.
echo.
pause
exit /b 1
