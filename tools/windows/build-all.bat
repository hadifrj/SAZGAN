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

title SAZGAN - Build

:MENU
cls
echo ============================================================
echo   SAZGAN - Build Center
echo ============================================================
echo.
echo   [1]  Client EXE        (dist\SazganClient\SazganClient.exe)
echo        Thin viewer only, no app code/DB. Points at a server.
echo        Opens in its own window (CEF) - no browser, Win 7 SP1+.
echo.
echo   [2]  Server Desktop EXE (dist\Sazgan\Sazgan.exe)
echo        Full app + window, runs standalone on one PC.
echo.
echo   [3]  Server Setup Wizard EXE (dist\SazganServerSetup.exe)
echo        Standalone installer-wizard exe for server machines.
echo.
echo   [4]  Windows Installer  (installer\output\Sazgan-Setup-*.exe)
echo        Packages the Server Desktop EXE with Inno Setup.
echo        Requires option [2] to be built first.
echo.
echo   [0]  Exit
echo ------------------------------------------------------------
set "CHOICE="
set /p CHOICE=Select option: 

if "%CHOICE%"=="1" goto BUILD_CLIENT
if "%CHOICE%"=="2" goto BUILD_SERVER
if "%CHOICE%"=="3" goto BUILD_WIZARD
if "%CHOICE%"=="4" goto BUILD_INSTALLER
if "%CHOICE%"=="0" goto END
echo.
echo [ERROR] Invalid option.
timeout /t 2 >nul
goto MENU

:NEED_PY
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
    echo [ERROR] Python was not found in PATH.
    echo Install Python from https://www.python.org/downloads/
    echo and check "Add python.exe to PATH" during setup.
    echo.
    pause
    goto MENU
)
%PY% --version
goto :eof

:NEED_PY39
set "PY39="
where py >nul 2>&1
if not errorlevel 1 (
    py -3.9 -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PY39=py -3.9"
)
if not defined PY39 (
    where python3.9 >nul 2>&1
    if not errorlevel 1 set "PY39=python3.9"
)
if not defined PY39 (
    echo.
    echo [ERROR] Python 3.9 was not found.
    echo cefpython3 (the embedded-browser engine used for the Client EXE
    echo so it opens in its own window on Windows 7+ instead of the
    echo system browser) only ships wheels up to Python 3.9. This is a
    echo BUILD-machine-only requirement - end users never need Python.
    echo.
    echo Install Python 3.9 from https://www.python.org/downloads/release/python-3913/
    echo ^(check "Add python.exe to PATH", or just make sure "py -3.9" works^)
    echo and run this again.
    echo.
    pause
    goto MENU
)
%PY39% --version
goto :eof

REM ============================================================
:BUILD_CLIENT
call :NEED_PY39
echo.
echo ============================================================
echo   Build CLIENT EXE (embedded window via CEF, no app code/DB)
echo ============================================================
echo [1/3] Installing client build requirements (Python 3.9)...
%PY39% -m pip install -r config\requirements-client.txt
if errorlevel 1 goto FAIL

echo [2/3] Running PyInstaller...
set "ICON_ARG="
if exist "static\favicon.ico" set "ICON_ARG=--icon static\favicon.ico"
if exist build rmdir /s /q build >nul 2>&1
if exist dist\SazganClient rmdir /s /q dist\SazganClient >nul 2>&1
REM onedir (not onefile): cefpython3 ships many loose binary/data files
REM (locales, .pak, subprocess.exe) that are fragile to extract from a
REM single-file bundle at runtime. --additional-hooks-dir pulls in the
REM official cefpython3 hook so PyInstaller collects them correctly.
%PY39% -m PyInstaller --noconfirm --clean --onedir --windowed --name SazganClient %ICON_ARG% --additional-hooks-dir desktop\pyinstaller_hooks desktop\client.py
if errorlevel 1 goto FAIL_PYINSTALLER

echo [3/3] Verifying output...
if not exist "dist\SazganClient\SazganClient.exe" goto FAIL_MISSING

echo.
echo [OK] dist\SazganClient\SazganClient.exe
echo Copy the whole "SazganClient" folder to any Windows 7+ PC on the
echo network and run SazganClient.exe; it will ask for the server address
echo once (--setup to change) and open it in its own window - no browser,
echo no WebView2/runtime install needed on the target PC.
echo ============================================================
pause
goto MENU

REM ============================================================
:BUILD_SERVER
call :NEED_PY
echo.
echo ============================================================
echo   Build SERVER DESKTOP EXE (full app, standalone)
echo ============================================================
echo [1/3] Installing desktop requirements...
%PY% -m pip install -r config\requirements-desktop.txt
if errorlevel 1 goto FAIL

echo [2/3] Running PyInstaller...
if exist build rmdir /s /q build >nul 2>&1
if exist dist\Sazgan rmdir /s /q dist\Sazgan >nul 2>&1
%PY% -m PyInstaller --noconfirm --clean --windowed --name Sazgan --add-data "templates;templates" --add-data "static;static" desktop\desktop.py
if errorlevel 1 goto FAIL_PYINSTALLER

echo [3/3] Verifying output...
if not exist "dist\Sazgan\Sazgan.exe" goto FAIL_MISSING

echo.
echo [OK] dist\Sazgan\Sazgan.exe
echo Run option [4] to wrap this into a Windows installer (Setup.exe).
echo ============================================================
pause
goto MENU

REM ============================================================
:BUILD_WIZARD
call :NEED_PY
echo.
echo ============================================================
echo   Build SERVER SETUP WIZARD EXE
echo ============================================================
%PY% -m pip install pyinstaller
if exist build\SazganServerSetup rmdir /s /q build\SazganServerSetup >nul 2>&1
if exist dist\SazganServerSetup.exe del /q dist\SazganServerSetup.exe >nul 2>&1
if exist runtime\python-3.11.9-amd64.exe (
  %PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name SazganServerSetup --add-data "runtime;runtime" installer\server_wizard.py
) else (
  echo [WARN] Python runtime not bundled - run scripts\prepare_runtime.bat first
  echo        for a fully offline EXE. Continuing without it...
  %PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name SazganServerSetup installer\server_wizard.py
)
if errorlevel 1 goto FAIL_PYINSTALLER
if not exist "dist\SazganServerSetup.exe" goto FAIL_MISSING

echo.
echo [OK] dist\SazganServerSetup.exe
echo ============================================================
pause
goto MENU

REM ============================================================
:BUILD_INSTALLER
echo.
echo ============================================================
echo   Build WINDOWS INSTALLER (Setup.exe via Inno Setup)
echo ============================================================
if exist "dist\Sazgan\Sazgan.exe" goto INSTALLER_HAVE_EXE
echo [ERROR] dist\Sazgan\Sazgan.exe not found.
echo Run option [2] first to build the Server Desktop EXE.
echo.
pause
goto MENU

:INSTALLER_HAVE_EXE
set "PF86=%ProgramFiles(x86)%"
set "PF64=%ProgramFiles%"
set "ISCC="
if exist "%PF86%\Inno Setup 6\ISCC.exe" set "ISCC=%PF86%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%PF64%\Inno Setup 6\ISCC.exe" set "ISCC=%PF64%\Inno Setup 6\ISCC.exe"
if not defined ISCC where ISCC.exe >nul 2>&1 && set "ISCC=ISCC.exe"

if defined ISCC goto INSTALLER_HAVE_ISCC
echo [ERROR] Inno Setup ISCC.exe was not found.
echo Install it from https://jrsoftware.org/isinfo.php then run this again.
echo.
pause
goto MENU

:INSTALLER_HAVE_ISCC
echo Using: %ISCC%
"%ISCC%" installer\Sazgan.iss
if errorlevel 1 goto FAIL

echo.
echo [OK] See installer\output\Sazgan-Setup-*.exe
echo ============================================================
pause
goto MENU

REM ============================================================
:FAIL_PYINSTALLER
echo.
echo [ERROR] PyInstaller failed. See the output above for details.
echo Common cause: antivirus/Windows Defender blocking PyInstaller
echo or the generated exe. Try adding an exclusion for this project
echo folder and run this again.
echo.
pause
goto MENU

:FAIL_MISSING
echo.
echo [WARNING] Build reported success but the expected output file
echo was not found. Check the PyInstaller output above for hidden errors.
echo.
pause
goto MENU

:FAIL
echo.
echo [ERROR] Step failed. See the output above for details.
echo.
pause
goto MENU

:END
endlocal
exit /b 0
