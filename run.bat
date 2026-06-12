@echo off
REM ============================================================
REM  BharatTrust AI - start the app (Windows)
REM  Launches the FastAPI backend which also serves the dashboard.
REM ============================================================
setlocal

cd /d "%~dp0backend"

if not exist ".venv\Scripts\activate.bat" (
  echo [ERROR] Environment not found. Run "setup.bat" first.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat

echo.
echo [BharatTrust AI] Starting server at http://localhost:8000
echo   - Dashboard : http://localhost:8000
echo   - API docs  : http://localhost:8000/docs
echo Press CTRL+C to stop.
echo.

REM open the dashboard in the default browser after a short delay
start "" cmd /c "timeout /t 3 >nul & start http://localhost:8000"

uvicorn app.main:app --host 0.0.0.0 --port 8000

endlocal
