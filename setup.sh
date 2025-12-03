#!/bin/bash
# ============================================
# Honduras Election 2025 - Setup Script
# For macOS/Linux Users
# ============================================

echo "============================================"
echo "Honduras Election 2025 - Setup"
echo "============================================"
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed."
    echo "Please install Python 3.8+ from https://www.python.org/downloads/"
    echo "Or use: brew install python3 (macOS with Homebrew)"
    exit 1
fi

echo "[OK] Python found: $(python3 --version)"

# Check if venv exists
if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
    echo "[OK] Virtual environment already exists."
else
    echo "[INFO] Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment."
        exit 1
    fi
    echo "[OK] Virtual environment created."
fi

# Activate virtual environment
echo "[INFO] Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if python3 -c "import streamlit" &> /dev/null; then
    echo "[OK] Dependencies already installed."
else
    echo "[INFO] Installing dependencies..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to install dependencies."
        exit 1
    fi
    echo "[OK] Dependencies installed."
fi

# Check if playwright browsers are installed
if python3 -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=True); b.close(); p.stop()" &> /dev/null; then
    echo "[OK] Playwright browsers already installed."
else
    echo "[INFO] Installing Playwright browsers..."
    playwright install chromium
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to install Playwright browsers."
        exit 1
    fi
    echo "[OK] Playwright browsers installed."
fi

echo
echo "============================================"
echo "Setup complete!"
echo "============================================"
echo
echo "To run the application, use: ./run.sh"
echo
echo "NOTE: On macOS, you'll need to use Chrome or Edge"
echo "instead of the built-in browser automation."
echo "The script is configured for Edge on Windows."
echo "You may need to modify main.py for macOS."
