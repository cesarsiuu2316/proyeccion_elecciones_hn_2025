#!/bin/bash
# ============================================
# Honduras Election 2025 - Run Script
# For macOS/Linux Users
# ============================================

echo "============================================"
echo "Honduras Election 2025 - Starting..."
echo "============================================"
echo

# Check if venv exists
if [ ! -f "venv/bin/activate" ]; then
    echo "[ERROR] Virtual environment not found."
    echo "Please run ./setup.sh first."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

echo "[INFO] Starting the scraper and dashboard..."
echo
echo "The scraper will run in the background."
echo "The dashboard will open in your browser."
echo
echo "Press Ctrl+C to stop both services."
echo

# Function to cleanup on exit
cleanup() {
    echo
    echo "[INFO] Stopping services..."
    if [ ! -z "$SCRAPER_PID" ]; then
        kill $SCRAPER_PID 2>/dev/null
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start the scraper in background
echo "[INFO] Starting scraper..."
python3 main.py &
SCRAPER_PID=$!

# Wait a moment for the scraper to start
sleep 3

# Start streamlit (this will block)
echo "[INFO] Starting Streamlit dashboard..."
streamlit run app.py

# If streamlit exits, cleanup
cleanup
