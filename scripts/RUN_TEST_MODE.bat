@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "RUN_TEST_MODE=1"
set "SAZGAN_DEMO_MODE=1"

echo [sazgan] TEST MODE enabled
echo [sazgan] RUN_TEST_MODE=%RUN_TEST_MODE%

where py >nul 2>&1
if not errorlevel 1 (
    py -3 app.py
    set "RC=%ERRORLEVEL%"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python was not found.
        set "RC=1"
    ) else (
        python app.py
        set "RC=%ERRORLEVEL%"
    )
)

pause
endlocal & exit /b %RC%
