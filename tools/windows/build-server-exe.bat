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

echo ============================================================
echo   SAZGAN - Build Desktop EXE
echo ============================================================
echo.

echo [1/4] Checking Python...
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] "python" was not found in PATH.
    echo Install Python from https://www.python.org/downloads/
    echo and make sure to check "Add python.exe to PATH" during setup.
    echo.
    pause
    exit /b 1
)
python --version
echo.

echo [2/4] Installing desktop requirements...
python -m pip install -r config\requirements-desktop.txt
if errorlevel 1 (
    echo.
    echo [ERROR] pip install failed. See the output above for details.
    echo Common causes: no internet connection, or "python" points to the
    echo Microsoft Store alias instead of a real Python install.
    echo.
    pause
    exit /b 1
)
echo.

echo [3/4] Running PyInstaller...
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name Sazgan ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  desktop\desktop.py
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller failed. See the output above for details.
    echo A common cause is antivirus/Windows Defender blocking PyInstaller
    echo or the generated exe. Try adding an exclusion for this project
    echo folder and run this script again.
    echo.
    pause
    exit /b 1
)
echo.

echo [4/4] Verifying output...
if not exist "dist\Sazgan\Sazgan.exe" (
    echo.
    echo [WARNING] Build reported success but dist\Sazgan\Sazgan.exe was not found.
    echo Check the PyInstaller output above for hidden errors.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Build finished successfully!
echo   Output: dist\Sazgan\Sazgan.exe
echo ============================================================
echo.
pause
