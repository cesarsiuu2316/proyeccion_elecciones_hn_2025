@echo off
REM ============================================
REM Honduras Election 2025 - Run Script
REM For Windows Users
REM ============================================

echo ============================================
echo Honduras Election 2025 - Starting...
echo ============================================
echo.

REM Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

echo [INFO] Starting the scraper and dashboard...
echo.
echo The scraper will open in a new window.
echo The dashboard will open in your browser.
echo.
echo Press Ctrl+C in each window to stop.
echo.

REM Start the scraper in a new window
start "Election Scraper" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && python main.py"

REM Wait a moment for the scraper to start
timeout /t 3 /nobreak >nul

REM Start streamlit in this window
echo [INFO] Starting Streamlit dashboard...
streamlit run app.py

pause
