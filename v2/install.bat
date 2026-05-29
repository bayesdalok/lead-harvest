@echo off
REM LeadHarvest — One-command installer (Windows)
echo.
echo   LeadHarvest - Installer
echo   -------------------------

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Python not found. Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)
echo   [OK] Python found

REM Create virtual environment
if not exist ".venv" (
    python -m venv .venv
    echo   [OK] Virtual environment created
)

call .venv\Scripts\activate.bat

REM Install dependencies
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo   [OK] Python packages installed

REM Install Playwright browser
playwright install chromium --with-deps
echo   [OK] Playwright Chromium installed

REM Create directories
if not exist "exports" mkdir exports
if not exist "logs"    mkdir logs
echo   [OK] Directories created

REM Copy .env
if not exist ".env" (
    copy .env.example .env
    echo   [OK] .env created
)

echo.
echo   Installation complete!
echo.
echo   To start LeadHarvest:
echo     .venv\Scripts\activate
echo     cd backend
echo     uvicorn main:app --reload
echo   Then open: http://127.0.0.1:8000
echo.
pause
