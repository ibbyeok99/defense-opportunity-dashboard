@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  python start_dashboard.py --setup
) else (
  py -3.14 start_dashboard.py --setup
)
if errorlevel 1 (
  echo Setup failed. See README.md.
  pause
  exit /b 1
)
pause
