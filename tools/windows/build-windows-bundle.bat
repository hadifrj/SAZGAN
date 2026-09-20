@echo off
setlocal EnableExtensions
set "SAZGAN_ROOT=%~dp0..\.."
cd /d "%SAZGAN_ROOT%"

@echo off
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
setlocal
cd /d "%SAZGAN_ROOT%"

echo ==========================================
echo Sazgan 1.0.0 - Windows Build
echo ==========================================

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3 -m venv venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat

python -m pip install --upgrade pip
python -m pip install -r config\requirements-desktop.txt

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

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
    echo BUILD FAILED.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo BUILD COMPLETE
echo EXE: dist\Sazgan\Sazgan.exe
echo ==========================================
pause
