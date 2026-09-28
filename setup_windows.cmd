@echo off
setlocal
cd /d "%~dp0"

set "VENV_PY=venv\Scripts\python.exe"

echo [1/4] Checking the project Python environment...
if not exist "%VENV_PY%" (
  echo The Python 3.11 virtual environment was not found. Creating it now...
  py -3.11 --version >nul 2>&1
  if errorlevel 1 (
    echo ERROR: Python 3.11 is required but the Windows Python launcher could not find it.
    echo Install Python 3.11, then run this file again.
    exit /b 1
  )
  py -3.11 -m venv venv
  if errorlevel 1 exit /b %errorlevel%
)

"%VENV_PY%" -c "import sys; print('Using:', sys.executable); print('Version:', sys.version.split()[0]); raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)"
if errorlevel 1 (
  echo ERROR: The existing venv is not Python 3.11.
  echo Recreate the venv with: py -3.11 -m venv venv
  exit /b 1
)

echo [2/4] Installing project dependencies into the venv...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 exit /b %errorlevel%

echo [3/4] Verifying installed dependencies...
"%VENV_PY%" -m pip check
if errorlevel 1 exit /b %errorlevel%

echo [4/4] Checking local configuration...
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Created .env from .env.example. Add your database, Gemini, and JWT values before starting.
) else (
  echo Existing .env preserved.
)

echo.
echo Setup complete.
echo Start the backend with: run_backend.cmd
echo Start the frontend in a second terminal with: run_frontend.cmd
exit /b 0
