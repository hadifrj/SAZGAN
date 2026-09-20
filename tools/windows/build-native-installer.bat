@echo off
setlocal EnableExtensions
set "SAZGAN_ROOT=%~dp0..\.."
cd /d "%SAZGAN_ROOT%"

@echo off
setlocal
cd /d "%SAZGAN_ROOT%"

echo ============================================================
echo   SAZGAN - Build NATIVE CLIENT INSTALLER (Setup.exe)
echo ============================================================
echo.

if not exist "dist\SazganNative\SazganNative.exe" (
    echo [ERROR] dist\SazganNative\SazganNative.exe not found.
    echo Run "Build Native Client EXE" first ^(Build ^& Release menu, option 4^).
    pause
    exit /b 1
)

where ISCC.exe >nul 2>&1
if not errorlevel 1 (
    set "ISCC=ISCC.exe"
) else (
    set "ISCC="
    if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
    if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe"
)
if not defined ISCC (
    echo Inno Setup compiler ^(ISCC.exe^) was not found in PATH or in the
    echo default install locations.
    echo Install Inno Setup, then run this file again.
    pause
    exit /b 1
)

"%ISCC%" installer\SazganNative.iss
if errorlevel 1 (
    echo.
    echo NATIVE CLIENT INSTALLER BUILD FAILED.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Build finished successfully!
echo   Installer created in installer\output\
echo ============================================================
echo.
pause
