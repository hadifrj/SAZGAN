@echo off
setlocal EnableExtensions
set "SAZGAN_ROOT=%~dp0..\.."
cd /d "%SAZGAN_ROOT%"

@echo off
setlocal EnableExtensions
cd /d "%SAZGAN_ROOT%"
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY echo Python not found.&pause&exit /b 1
%PY% -m pip install pyinstaller
if exist build\SazganServerSetup rmdir /s /q build\SazganServerSetup
if exist dist\SazganServerSetup.exe del /q dist\SazganServerSetup.exe
if exist runtime\python-3.11.9-amd64.exe (
  %PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name SazganServerSetup --add-data "runtime;runtime" installer\server_wizard.py
) else (
  echo [WARN] Python Runtime is not bundled. Run scripts\prepare_runtime.bat first for a fully offline EXE.
  %PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name SazganServerSetup installer\server_wizard.py
)
if errorlevel 1 echo BUILD FAILED.&pause&exit /b 1
echo.
echo [OK] dist\SazganServerSetup.exe
echo.
pause
