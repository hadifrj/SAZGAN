@echo off
setlocal EnableExtensions
set "SAZGAN_ROOT=%~dp0..\.."
cd /d "%SAZGAN_ROOT%"

@echo off
setlocal EnableExtensions
cd /d "%SAZGAN_ROOT%"
if not exist runtime mkdir runtime
set "OUT=%cd%\runtime\python-3.11.9-amd64.exe"
where powershell >nul 2>&1 || (echo [ERROR] PowerShell not found.&pause&exit /b 1)
echo Downloading official Python 3.11.9 x64 runtime...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%OUT%'"
if errorlevel 1 (echo [ERROR] Download failed.&pause&exit /b 1)
if not exist "%OUT%" (echo [ERROR] Runtime file missing.&pause&exit /b 1)
for %%A in ("%OUT%") do if %%~zA LSS 10000000 (echo [ERROR] Runtime file is too small.&del /q "%OUT%"&pause&exit /b 1)
echo [OK] %OUT%
pause
