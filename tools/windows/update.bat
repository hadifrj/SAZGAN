@echo off
setlocal EnableExtensions
set "SAZGAN_ROOT=%~dp0..\.."
cd /d "%SAZGAN_ROOT%"

@echo off
setlocal EnableExtensions
cd /d "%SAZGAN_ROOT%"
chcp 65001 >nul 2>&1
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
  echo [ERROR] Python not found.
  pause
  exit /b 1
)
if "%~1"=="" (
  echo Usage: scripts\update.bat "path\to\SAZGAN-update.zip"
  echo.
  pause
  exit /b 2
)
%PY% scripts\update.py --package "%~1"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (echo [OK] Update completed.) else (echo [ERROR] Update failed.)
pause
exit /b %RC%
