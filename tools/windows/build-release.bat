@echo off
setlocal EnableExtensions
set "SAZGAN_ROOT=%~dp0..\.."
cd /d "%SAZGAN_ROOT%"

@echo off
chcp 65001 >nul
cd /d "%SAZGAN_ROOT%"

echo.
echo === SAZGAN Release Build ===
echo.
echo Running release validation...
python scripts\release_check.py
if errorlevel 1 (
  echo.
  echo Release validation failed. Build cancelled.
  pause
  exit /b 1
)
echo Release validation passed.
echo.

if "%~1"=="" (
  python scripts\build_release.py
) else (
  python scripts\build_release.py %*
)

if errorlevel 1 (
  echo.
  echo Build failed.
  pause
  exit /b 1
)

echo.
echo Output is available in the dist folder.
pause
