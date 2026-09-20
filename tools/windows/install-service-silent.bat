@echo off
setlocal EnableExtensions
set "SAZGAN_ROOT=%~dp0..\.."
cd /d "%SAZGAN_ROOT%"

@echo off
chcp 65001 >nul
cd /d "%SAZGAN_ROOT%"
setlocal EnableDelayedExpansion
REM Silent variant of install_service.bat for use by the Setup installer.
REM Same logic, but never blocks on "pause" so it can run unattended.

set PY=
where py >nul 2>&1 && set PY=py -3
if not defined PY (
  where python >nul 2>&1 && set PY=python
)
if not defined PY (
  echo [ERROR] Python was not found. > "%SAZGAN_ROOT%\logs\service-install-error.log"
  exit /b 1
)

%PY% -c "import flask" 2>nul
if errorlevel 1 (
  if exist "offline_packages\" (
    %PY% -m pip install --no-index --find-links "offline_packages" -r requirements.txt >nul 2>&1
  ) else (
    %PY% -m pip install -r requirements.txt >nul 2>&1
  )
)
if exist "offline_packages\" (
  %PY% -m pip install --no-index --find-links "offline_packages" waitress -q >nul 2>&1
) else (
  %PY% -m pip install waitress -q >nul 2>&1
)

cd /d "%SAZGAN_ROOT%"
set APPDIR=%cd%
set RUNNER=%APPDIR%\scripts\run_as_service.py
set SERVICE_NAME=SazganService
set NSSM=%APPDIR%\tools\nssm.exe

if not exist "%RUNNER%" exit /b 1

for /f "delims=" %%i in ('%PY% -c "import sys; print(sys.executable)"') do set PYTHON_EXE=%%i

if exist "%NSSM%" (
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
  exit /b 0
)

schtasks /Delete /TN "SazganService" /F >nul 2>&1
schtasks /Create /TN "SazganService" /SC ONSTART /RL HIGHEST /RU SYSTEM /TR "\"%PYTHON_EXE%\" \"%RUNNER%\"" /F >nul 2>&1
if errorlevel 1 (
  schtasks /Create /TN "SazganService" /SC ONLOGON /RL HIGHEST /TR "\"%PYTHON_EXE%\" \"%RUNNER%\"" /F >nul 2>&1
)
schtasks /Run /TN "SazganService" >nul 2>&1
exit /b 0
