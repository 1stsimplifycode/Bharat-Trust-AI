@echo off
REM ============================================================
REM  BharatTrust AI - one-time setup (Windows)
REM  Creates a virtual environment, installs deps, seeds the DB.
REM ============================================================
setlocal

echo.
echo [BharatTrust AI] Setup starting...
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found on PATH. Install Python 3.10+ from python.org and retry.
  pause
  exit /b 1
)

cd /d "%~dp0backend"

echo [1/4] Creating virtual environment...
python -m venv .venv
if errorlevel 1 ( echo [ERROR] venv creation failed. & pause & exit /b 1 )

echo [2/4] Activating environment...
call .venv\Scripts\activate.bat

echo [3/4] Installing dependencies (this can take a couple minutes)...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 ( echo [ERROR] dependency install failed. & pause & exit /b 1 )

echo [4/4] Seeding the database with demo data...
python -m app.seed
if errorlevel 1 ( echo [ERROR] seeding failed. & pause & exit /b 1 )

echo.
echo [BharatTrust AI] Setup complete. Run "run.bat" to start the app.
echo.
pause
endlocal
