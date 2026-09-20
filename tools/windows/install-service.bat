@echo off
setlocal EnableExtensions
set "SAZGAN_ROOT=%~dp0..\.."
cd /d "%SAZGAN_ROOT%"

@echo off
chcp 65001 >nul
cd /d "%SAZGAN_ROOT%"
setlocal EnableDelayedExpansion

echo ============================================
echo   Install SAZGAN background service (Windows)
echo ============================================
echo.

REM Find Python
set PY=
where py >nul 2>&1 && set PY=py -3
if not defined PY (
  where python >nul 2>&1 && set PY=python
)
if not defined PY (
  echo [ERROR] Python was not found. Install it from python.org and enable PATH.
  pause
  exit /b 1
)

echo Python: %PY%
%PY% -c "import flask" 2>nul
if errorlevel 1 (
  echo Checking offline dependency bundle...
  if exist "offline_packages\" (
    %PY% -m pip install --no-index --find-links "offline_packages" -r requirements.txt
  ) else (
    echo Installing dependencies from configured package index...
    %PY% -m pip install -r requirements.txt
  )
  if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    exit /b 1
  )
)
if exist "offline_packages\" (
  %PY% -m pip install --no-index --find-links "offline_packages" waitress -q
) else (
  %PY% -m pip install waitress -q 2>nul
)

cd /d "%SAZGAN_ROOT%"
set APPDIR=%cd%
set RUNNER=%APPDIR%\scripts\run_as_service.py
set SERVICE_NAME=SazganService
set NSSM=%APPDIR%\tools\nssm.exe

if not exist "%RUNNER%" (
  echo [ERROR] scripts\run_as_service.py was not found.
  pause
  exit /b 1
)

REM Resolve the actual python.exe path
for /f "delims=" %%i in ('%PY% -c "import sys; print(sys.executable)"') do set PYTHON_EXE=%%i
echo Executable: %PYTHON_EXE%
echo Runner: %RUNNER%
echo.

if exist "%NSSM%" (
  echo Installing with NSSM...
  "%NSSM%" stop %SERVICE_NAME% >nul 2>&1
  "%NSSM%" remove %SERVICE_NAME% confirm >nul 2>&1
  "%NSSM%" install %SERVICE_NAME% "%PYTHON_EXE%" "%RUNNER%"
  "%NSSM%" set %SERVICE_NAME% AppDirectory "%APPDIR%"
  "%NSSM%" set %SERVICE_NAME% DisplayName "Sazgan After-Sales Service"
  "%NSSM%" set %SERVICE_NAME% Description "SAZGAN After-Sales Service Platform"
  "%NSSM%" set %SERVICE_NAME% Start SERVICE_AUTO_START
  "%NSSM%" set %SERVICE_NAME% AppStdout "%APPDIR%\logs\service-stdout.log"
  "%NSSM%" set %SERVICE_NAME% AppStderr "%APPDIR%\logs\service-stderr.log"
  "%NSSM%" set %SERVICE_NAME% AppRotateFiles 1
  "%NSSM%" set %SERVICE_NAME% AppRotateBytes 2000000
  "%NSSM%" start %SERVICE_NAME%
  echo.
  echo [OK] Service %SERVICE_NAME% installed and started.
  echo Manage it with: services.msc or:
  echo   "%NSSM%" status %SERVICE_NAME%
  echo   "%NSSM%" stop %SERVICE_NAME%
  echo   "%NSSM%" start %SERVICE_NAME%
  goto :done
)

echo NSSM is not available at tools\nssm.exe - installing via Task Scheduler...
echo.

schtasks /Delete /TN "SazganService" /F >nul 2>&1
schtasks /Create /TN "SazganService" /SC ONSTART /RL HIGHEST /RU SYSTEM /TR "\"%PYTHON_EXE%\" \"%RUNNER%\"" /F
if errorlevel 1 (
  echo Trying with the current user...
  schtasks /Create /TN "SazganService" /SC ONLOGON /RL HIGHEST /TR "\"%PYTHON_EXE%\" \"%RUNNER%\"" /F
)

echo Starting immediately...
schtasks /Run /TN "SazganService" >nul 2>&1

echo.
echo [OK] Scheduled task SazganService registered.
echo It is configured to start automatically with Windows.
echo For a more reliable service: place NSSM at tools\nssm.exe and run this file again.
echo NSSM download: https://nssm.cc/download

:done
echo.
echo Test: Browser -> http://127.0.0.1:5000
echo Log: logs\service.log
echo.
pause
