@echo off
REM ============================================
REM Honduras Election 2025 - Setup Script
REM For Windows Users
REM ============================================

echo ============================================
echo Honduras Election 2025 - Setup
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python found.

REM Check if venv exists
if exist "venv\Scripts\activate.bat" (
    echo [OK] Virtual environment already exists.
) else (
    echo [INFO] Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies (always run pip install, it handles already-installed packages)
echo [INFO] Installing/checking dependencies...
pip install -r requirements.txt --quiet
echo [OK] Dependencies ready.

REM Install playwright browsers
echo [INFO] Installing/checking Playwright browsers...
playwright install chromium >nul 2>&1
echo [OK] Playwright browsers ready.

echo.
echo ============================================
echo Setup complete!
echo ============================================
echo.
echo To run the application, use: run.bat
echo.
pause
