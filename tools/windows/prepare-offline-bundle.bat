@echo off
setlocal EnableExtensions
set "SAZGAN_ROOT=%~dp0..\.."
cd /d "%SAZGAN_ROOT%"

@echo off
setlocal EnableExtensions
cd /d "%SAZGAN_ROOT%"

echo ============================================
echo   SAZGAN Offline Dependency Bundle Builder
echo ============================================
echo.

set PY=
where py >nul 2>&1 && set PY=py -3.11
if not defined PY where python >nul 2>&1 && set PY=python
if not defined PY (
  echo [ERROR] Python 3.11 was not found.
  echo Install Python 3.11 x64 on this build PC and run again.
  pause
  exit /b 1
)

%PY% -c "import sys; print('Python:', sys.version); raise SystemExit(0 if sys.version_info[:2]==(3,11) else 2)"
if errorlevel 2 (
  echo [ERROR] This offline bundle builder requires CPython 3.11.
  pause
  exit /b 1
)

if not exist offline_packages mkdir offline_packages

echo [1/2] Downloading Windows x64 wheels...
%PY% -m pip download -r requirements.txt -d offline_packages --only-binary=:all: --platform win_amd64 --python-version 311 --implementation cp --abi cp311 --no-deps
if errorlevel 1 (
  echo [ERROR] Some packages could not be downloaded.
  pause
  exit /b 1
)

REM Download dependencies transitively using pip's normal resolver into the same folder.
%PY% -m pip download -r requirements.txt -d offline_packages --only-binary=:all: --platform win_amd64 --python-version 311 --implementation cp --abi cp311
if errorlevel 1 (
  echo [ERROR] Dependency bundle build failed.
  pause
  exit /b 1
)

echo [2/2] Verifying bundle...
%PY% -m pip install --dry-run --no-index --find-links offline_packages -r requirements.txt > offline_packages\verify.txt 2>&1
if errorlevel 1 (
  echo [ERROR] Offline dependency verification failed.
  type offline_packages\verify.txt
  pause
  exit /b 1
)

echo.
echo [OK] Offline dependency bundle is ready.
echo Location: %cd%\offline_packages
echo Copy the whole project including offline_packages to the offline server.
echo.
pause
