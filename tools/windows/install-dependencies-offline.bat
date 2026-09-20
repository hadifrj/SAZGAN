@echo off
setlocal EnableExtensions
set "SAZGAN_ROOT=%~dp0..\.."
cd /d "%SAZGAN_ROOT%"

@echo off
setlocal
cd /d "%SAZGAN_ROOT%"
set PY=
where py >nul 2>&1 && set PY=py -3.11
if not defined PY where python >nul 2>&1 && set PY=python
if not defined PY (
  echo [ERROR] Python 3.11 was not found.
  exit /b 1
)
if not exist offline_packages\ (
  echo [ERROR] offline_packages folder is missing.
  exit /b 1
)
%PY% -m pip install --no-index --find-links offline_packages -r requirements.txt
if errorlevel 1 exit /b 1
%PY% -m pip install --no-index --find-links offline_packages waitress
if errorlevel 1 exit /b 1
echo [OK] Offline dependencies installed.
