@echo off
setlocal EnableExtensions
set "SAZGAN_ROOT=%~dp0..\.."
cd /d "%SAZGAN_ROOT%"

@echo off
setlocal
cd /d "%SAZGAN_ROOT%"

where ISCC.exe >nul 2>&1
if errorlevel 1 (
    echo Inno Setup compiler (ISCC.exe) was not found in PATH.
    echo Install Inno Setup, then run this file again.
    pause
    exit /b 1
)

ISCC.exe installer\Sazgan.iss
if errorlevel 1 (
    echo INSTALLER BUILD FAILED.
    pause
    exit /b 1
)

echo Installer created in installer\output\
pause
