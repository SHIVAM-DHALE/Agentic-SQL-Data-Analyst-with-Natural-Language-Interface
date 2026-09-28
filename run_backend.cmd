@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo ERROR: Project virtual environment was not found.
  echo Run setup_windows.cmd first.
  exit /b 1
)
"venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)"
if errorlevel 1 (
  echo ERROR: The project venv must use Python 3.11.
  echo Move the incompatible venv aside, then run setup_windows.cmd.
  exit /b 1
)
"venv\Scripts\python.exe" -m database.migrate
if errorlevel 1 exit /b %errorlevel%
"venv\Scripts\python.exe" -m uvicorn api.main:app --reload
