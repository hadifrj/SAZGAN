@echo off
setlocal EnableExtensions
set "SAZGAN_ROOT=%~dp0..\.."
cd /d "%SAZGAN_ROOT%"

@echo off
setlocal
cd /d "%SAZGAN_ROOT%"

if not exist "dist\Sazgan\Sazgan.exe" (
  echo Build the EXE first.
  exit /b 1
)

echo Inno Setup is required to compile installer\Sazgan.iss
echo The installer uses the standard step-by-step Windows wizard.
pause
