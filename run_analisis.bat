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

python analisis.py %*

pause
