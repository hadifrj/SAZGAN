@echo off
setlocal EnableExtensions EnableDelayedExpansion
title SAZGAN Control Center
color 0B

REM ============================================================
REM SAZGAN CONTROL CENTER
REM Root launcher only. Child BAT files live under tools\windows.
REM ============================================================

set "SAZGAN_ROOT=%~dp0"
if not "%SAZGAN_ROOT:~-1%"=="\" set "SAZGAN_ROOT=%SAZGAN_ROOT%\"
set "SAZGAN_HOST=0.0.0.0"
set "SAZGAN_PORT=5000"
set "SAZGAN_VERSION=4.9.6"
set "PY="

REM Detect Python executable without launching Python before the menu.
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    where python >nul 2>&1
    if not errorlevel 1 set "PY=python"
)

:MAIN_MENU
@echo off
cls
echo.
echo ============================================================================
echo                         SAZGAN CONTROL CENTER
echo                              Version %SAZGAN_VERSION%
echo ============================================================================
echo.
if defined PY (
    echo   Python ............. %PY%
) else (
    echo   Python ............. NOT FOUND
)
echo   Server URL .......... http://127.0.0.1:%SAZGAN_PORT%
echo   Project Root ........ %SAZGAN_ROOT%
echo.
echo ----------------------------------------------------------------------------
echo   [1]  START
echo   [2]  BUILD ^& RELEASE
echo   [3]  SETUP ^& INSTALLATION
echo   [4]  MAINTENANCE
echo   [5]  DOCUMENTATION
echo.
echo   [0]  EXIT
echo ----------------------------------------------------------------------------
echo.
choice /c 123450 /n /m "Select an option: "
if errorlevel 6 goto END
if errorlevel 5 goto DOCS_MENU
if errorlevel 4 goto MAINTENANCE_MENU
if errorlevel 3 goto SETUP_MENU
if errorlevel 2 goto BUILD_MENU
if errorlevel 1 goto START_MENU
goto MAIN_MENU

:START_MENU
@echo off
cls
echo.
echo ============================================================================
echo                            SAZGAN ^> START
echo ============================================================================
echo.
echo   [1]  Start SAZGAN Server
echo   [2]  Open SAZGAN in Browser
echo.
echo   [B]  Back
echo   [0]  Main Menu
echo ----------------------------------------------------------------------------
echo.
choice /c 12B0 /n /m "Select an option: "
if errorlevel 4 goto MAIN_MENU
if errorlevel 3 goto MAIN_MENU
if errorlevel 2 goto BROWSER
if errorlevel 1 goto RUN_SERVER
goto START_MENU

:BUILD_MENU
@echo off
cls
echo.
echo ============================================================================
echo                         SAZGAN ^> BUILD ^& RELEASE
echo ============================================================================
echo.
echo   [1]  Build Full Release ZIP
echo   [2]  Build Server EXE
echo   [3]  Build Web Client EXE
echo   [4]  Build Native Client EXE
echo   [5]  Build Lite Client EXE
echo   [6]  Build Server Installation Wizard
echo   [7]  Build Windows Bundle
echo   [8]  Build Installer Package
echo   [9]  Build All
echo   [N]  Build Native Client Installer (Setup.exe)
echo.
echo   [B]  Back
echo   [0]  Main Menu
echo ----------------------------------------------------------------------------
echo.
choice /c 123456789NB0 /n /m "Select an option: "
if errorlevel 12 goto MAIN_MENU
if errorlevel 11 goto MAIN_MENU
if errorlevel 10 goto BUILD_NATIVE_INSTALLER
if errorlevel 9 goto BUILD_ALL
if errorlevel 8 goto BUILD_INSTALLER
if errorlevel 7 goto BUILD_WINDOWS
if errorlevel 6 goto BUILD_WIZARD
if errorlevel 5 goto BUILD_LITE
if errorlevel 4 goto BUILD_NATIVE
if errorlevel 3 goto BUILD_CLIENT
if errorlevel 2 goto BUILD_SERVER
if errorlevel 1 goto BUILD_RELEASE
goto BUILD_MENU

:SETUP_MENU
@echo off
cls
echo.
echo ============================================================================
echo                     SAZGAN ^> SETUP ^& INSTALLATION
echo ============================================================================
echo.
echo   [1]  Install Dependencies Online
echo   [2]  Install Dependencies Offline
echo   [3]  Prepare Offline Packages
echo   [4]  Prepare Python Runtime
echo   [5]  Server Installation Wizard
echo   [6]  Install / Register Windows Service
echo   [7]  Install Windows Service (Silent)
echo   [8]  Update Existing Installation
echo.
echo   [B]  Back
echo   [0]  Main Menu
echo ----------------------------------------------------------------------------
echo.
choice /c 12345678B0 /n /m "Select an option: "
if errorlevel 10 goto MAIN_MENU
if errorlevel 9 goto MAIN_MENU
if errorlevel 8 goto UPDATE
if errorlevel 7 goto INSTALL_SVC_SILENT
if errorlevel 6 goto INSTALL_SVC
if errorlevel 5 goto SERVER_WIZARD
if errorlevel 4 goto PREP_RUNTIME
if errorlevel 3 goto PREP_OFFLINE
if errorlevel 2 goto INSTALL_OFFLINE
if errorlevel 1 goto INSTALL_ONLINE
goto SETUP_MENU

:MAINTENANCE_MENU
@echo off
cls
echo.
echo ============================================================================
echo                        SAZGAN ^> MAINTENANCE
echo ============================================================================
echo.
echo   [1]  Health Check
echo   [2]  Smoke Test
echo   [3]  Run Test Mode
echo   [4]  Windows Service Menu
echo   [5]  Open Project Folder
echo   [6]  Open Tools Folder
echo.
echo   [B]  Back
echo   [0]  Main Menu
echo ----------------------------------------------------------------------------
echo.
choice /c 123456B0 /n /m "Select an option: "
if errorlevel 8 goto MAIN_MENU
if errorlevel 7 goto MAIN_MENU
if errorlevel 6 goto OPEN_TOOLS
if errorlevel 5 goto OPEN_PROJECT
if errorlevel 4 goto SERVICE_MENU
if errorlevel 3 goto RUN_TEST_MODE
if errorlevel 2 goto SMOKE
if errorlevel 1 goto HEALTH
goto MAINTENANCE_MENU

:DOCS_MENU
@echo off
cls
echo.
echo ============================================================================
echo                       SAZGAN ^> DOCUMENTATION
echo ============================================================================
echo.
echo   [1]  Project Structure Guide
echo   [2]  Windows Tools Guide
echo   [3]  Open Documentation Folder
echo.
echo   [B]  Back
echo   [0]  Main Menu
echo ----------------------------------------------------------------------------
echo.
choice /c 123B0 /n /m "Select an option: "
if errorlevel 5 goto MAIN_MENU
if errorlevel 4 goto MAIN_MENU
if errorlevel 3 goto OPEN_DOCS
if errorlevel 2 goto DOC_WINDOWS
if errorlevel 1 goto DOC_STRUCTURE
goto DOCS_MENU

:RUN_SERVER
call :NEED_PY
if errorlevel 1 goto START_MENU
call :HEADER "START SAZGAN SERVER"
pushd "%SAZGAN_ROOT%"
echo Checking application dependencies...
%PY% -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo Installing requirements...
    %PY% -m pip install -r "%SAZGAN_ROOT%requirements.txt"
    if errorlevel 1 (
        popd
        echo [ERROR] Dependency installation failed.
        pause
        goto START_MENU
    )
)
%PY% -c "import cryptography" >nul 2>&1
if errorlevel 1 (
    echo Installing Web Push dependencies...
    %PY% -m pip install "cryptography>=41.0" "pywebpush>=1.14" "py-vapid>=1.9" -q
)
netsh advfirewall firewall show rule name="SAZGAN 5000" >nul 2>&1
if errorlevel 1 (
    netsh advfirewall firewall add rule name="SAZGAN 5000" dir=in action=allow protocol=TCP localport=5000 >nul 2>&1
)
echo.
echo   Status ........ RUNNING
echo   Local URL ..... http://127.0.0.1:%SAZGAN_PORT%
echo   Network ....... Use the server LAN address shown by ipconfig.
echo   Stop .......... Ctrl+C
echo.
%PY% "%SAZGAN_ROOT%app.py"
set "RC=%ERRORLEVEL%"
popd
echo.
if "%RC%"=="0" (
    echo Application stopped normally.
) else (
    echo Application stopped with exit code %RC%.
)
pause
goto START_MENU

:BROWSER
start "" "http://127.0.0.1:%SAZGAN_PORT%"
echo [OK] Browser opened.
timeout /t 2 >nul
goto START_MENU

:BUILD_RELEASE
call :RUN_BAT "tools\windows\build-release.bat" "BUILD FULL RELEASE ZIP"
goto BUILD_MENU

:BUILD_SERVER
call :RUN_BAT "tools\windows\build-server-exe.bat" "BUILD SERVER EXE"
goto BUILD_MENU

:BUILD_CLIENT
call :RUN_BAT "tools\windows\build-client-exe.bat" "BUILD WEB CLIENT EXE"
goto BUILD_MENU

:BUILD_NATIVE
call :RUN_BAT "tools\windows\build-native-client.bat" "BUILD NATIVE CLIENT EXE"
goto BUILD_MENU

:BUILD_LITE
call :RUN_BAT "tools\windows\build-client-lite.bat" "BUILD LITE CLIENT EXE"
goto BUILD_MENU

:BUILD_WIZARD
call :RUN_BAT "tools\windows\build-server-wizard.bat" "BUILD SERVER INSTALLATION WIZARD"
goto BUILD_MENU

:BUILD_WINDOWS
call :RUN_BAT "tools\windows\build-windows-bundle.bat" "BUILD WINDOWS BUNDLE"
goto BUILD_MENU

:BUILD_INSTALLER
call :RUN_BAT "tools\windows\build-installer-package.bat" "BUILD INSTALLER PACKAGE"
goto BUILD_MENU

:BUILD_ALL
call :RUN_BAT "tools\windows\build-all.bat" "BUILD ALL"
goto BUILD_MENU

:BUILD_NATIVE_INSTALLER
call :RUN_BAT "tools\windows\build-native-installer.bat" "BUILD NATIVE CLIENT INSTALLER"
goto BUILD_MENU

:UPDATE
call :NEED_PY
if errorlevel 1 goto SETUP_MENU
call :HEADER "UPDATE EXISTING INSTALLATION"
echo Enter the path to the update ZIP package.
echo.
set "UPDATE_ZIP="
set /p "UPDATE_ZIP=Update ZIP path: "
if not defined UPDATE_ZIP goto SETUP_MENU
if not exist "%UPDATE_ZIP%" (
    echo [ERROR] ZIP file not found.
    pause
    goto SETUP_MENU
)
call :RUN_BAT "tools\windows\update.bat" "UPDATE EXISTING INSTALLATION" "%UPDATE_ZIP%"
goto SETUP_MENU

:SERVER_WIZARD
call :NEED_PY
if errorlevel 1 goto SETUP_MENU
call :HEADER "SERVER INSTALLATION WIZARD"
if not exist "%SAZGAN_ROOT%installer\server_wizard.py" (
    echo [ERROR] installer\server_wizard.py not found.
    pause
    goto SETUP_MENU
)
pushd "%SAZGAN_ROOT%"
%PY% "installer\server_wizard.py"
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" echo [ERROR] Wizard exited with code %RC%.
pause
goto SETUP_MENU

:INSTALL_SVC
call :RUN_BAT "tools\windows\install-service.bat" "INSTALL WINDOWS SERVICE"
goto SETUP_MENU

:INSTALL_SVC_SILENT
call :RUN_BAT "tools\windows\install-service-silent.bat" "INSTALL WINDOWS SERVICE - SILENT"
goto SETUP_MENU

:INSTALL_ONLINE
call :RUN_BAT "tools\windows\install-dependencies-online.bat" "INSTALL DEPENDENCIES - ONLINE"
goto SETUP_MENU

:INSTALL_OFFLINE
call :RUN_BAT "tools\windows\install-dependencies-offline.bat" "INSTALL DEPENDENCIES - OFFLINE"
goto SETUP_MENU

:PREP_OFFLINE
call :RUN_BAT "tools\windows\prepare-offline-bundle.bat" "PREPARE OFFLINE PACKAGES"
goto SETUP_MENU

:PREP_RUNTIME
call :RUN_BAT "tools\windows\prepare-runtime.bat" "PREPARE PYTHON RUNTIME"
goto SETUP_MENU

:SERVICE_MENU
@echo off
cls
echo.
echo ============================================================================
echo                    SAZGAN ^> WINDOWS SERVICE
echo ============================================================================
echo.
echo   [1]  Install / Register Service
echo   [2]  Start Service
echo   [3]  Stop Service
echo   [4]  Show Service Status
echo.
echo   [B]  Back
echo   [0]  Main Menu
echo ----------------------------------------------------------------------------
echo.
choice /c 1234B0 /n /m "Select an option: "
if errorlevel 6 goto MAIN_MENU
if errorlevel 5 goto MAINTENANCE_MENU
if errorlevel 4 goto STATUS_SVC
if errorlevel 3 goto STOP_SVC
if errorlevel 2 goto START_SVC
if errorlevel 1 goto INSTALL_SVC
goto SERVICE_MENU

:START_SVC
call :HEADER "START WINDOWS SERVICE"
if exist "%SAZGAN_ROOT%tools\nssm.exe" (
    "%SAZGAN_ROOT%tools\nssm.exe" start SazganService
) else (
    sc start SazganService
)
pause
goto SERVICE_MENU

:STOP_SVC
call :HEADER "STOP WINDOWS SERVICE"
if exist "%SAZGAN_ROOT%tools\nssm.exe" (
    "%SAZGAN_ROOT%tools\nssm.exe" stop SazganService
) else (
    sc stop SazganService
)
pause
goto SERVICE_MENU

:STATUS_SVC
call :HEADER "WINDOWS SERVICE STATUS"
if exist "%SAZGAN_ROOT%tools\nssm.exe" (
    "%SAZGAN_ROOT%tools\nssm.exe" status SazganService
) else (
    sc query SazganService
)
pause
goto SERVICE_MENU

:HEALTH
call :NEED_PY
if errorlevel 1 goto MAINTENANCE_MENU
call :HEADER "HEALTH CHECK"
if exist "%SAZGAN_ROOT%scripts\health_check.py" (
    pushd "%SAZGAN_ROOT%"
    %PY% "scripts\health_check.py"
    set "RC=%ERRORLEVEL%"
    popd
    if not "%RC%"=="0" echo [ERROR] Health check exited with code %RC%.
) else (
    echo [ERROR] scripts\health_check.py not found.
)
pause
goto MAINTENANCE_MENU

:RUN_TEST_MODE
call :RUN_BAT "scripts\RUN_TEST_MODE.bat" "RUN TEST MODE"
goto MAINTENANCE_MENU

:SMOKE
call :NEED_PY
if errorlevel 1 goto MAINTENANCE_MENU
call :HEADER "SMOKE TEST"
if exist "%SAZGAN_ROOT%scripts\smoke_test.py" (
    pushd "%SAZGAN_ROOT%"
    %PY% "scripts\smoke_test.py"
    set "RC=%ERRORLEVEL%"
    popd
    if not "%RC%"=="0" echo [ERROR] Smoke test exited with code %RC%.
) else (
    echo [ERROR] scripts\smoke_test.py not found.
)
pause
goto MAINTENANCE_MENU

:OPEN_PROJECT
start "" explorer.exe "%SAZGAN_ROOT%"
goto MAINTENANCE_MENU

:OPEN_TOOLS
start "" explorer.exe "%SAZGAN_ROOT%tools"
goto MAINTENANCE_MENU

:DOC_STRUCTURE
if exist "%SAZGAN_ROOT%docs\README.md" (
    start "" "%SAZGAN_ROOT%docs\README.md"
) else (
    echo [ERROR] docs\README.md not found.
    pause
)
goto DOCS_MENU

:DOC_WINDOWS
if exist "%SAZGAN_ROOT%tools\windows\README.md" (
    start "" "%SAZGAN_ROOT%tools\windows\README.md"
) else (
    echo [ERROR] tools\windows\README.md not found.
    pause
)
goto DOCS_MENU

:OPEN_DOCS
start "" explorer.exe "%SAZGAN_ROOT%docs"
goto DOCS_MENU

:RUN_BAT
set "BAT_FILE=%~1"
set "BAT_TITLE=%~2"
set "BAT_ARG=%~3"
call :HEADER "%BAT_TITLE%"
if not exist "%SAZGAN_ROOT%%BAT_FILE%" (
    echo [ERROR] Tool not found:
    echo         %SAZGAN_ROOT%%BAT_FILE%
    pause
    exit /b 1
)
pushd "%SAZGAN_ROOT%"
if defined BAT_ARG (
    call "%SAZGAN_ROOT%%BAT_FILE%" "%BAT_ARG%"
) else (
    call "%SAZGAN_ROOT%%BAT_FILE%"
)
set "RC=%ERRORLEVEL%"
popd
@echo off
if "%RC%"=="0" (
    echo.
    echo [OK] Operation completed successfully.
) else (
    echo.
    echo [ERROR] Operation failed. Exit code: %RC%
)
pause
exit /b %RC%

:NEED_PY
if not defined PY (
    echo.
    echo [ERROR] Python was not found.
    echo Use Setup ^& Installation to install/configure Python.
    pause
    exit /b 1
)
%PY% -c "import sys" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python launcher was found but could not start Python.
    echo Check the Python installation.
    pause
    exit /b 1
)
exit /b 0

:HEADER
@echo off
cls
echo.
echo ============================================================================
echo                            SAZGAN
echo                         %~1
echo ============================================================================
echo.
exit /b 0

:END
@echo off
cls
echo.
echo ============================================================================
echo                         SAZGAN CONTROL CENTER
echo                              Goodbye
echo ============================================================================
echo.
endlocal
exit /b 0
