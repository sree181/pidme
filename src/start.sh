#!/bin/bash
# PIDME startup script — installs deps and launches backend + frontend
set -e

echo ""
echo "  ██████╗ ██╗██████╗ ███╗   ███╗███████╗"
echo "  ██╔══██╗██║██╔══██╗████╗ ████║██╔════╝"
echo "  ██████╔╝██║██║  ██║██╔████╔██║█████╗  "
echo "  ██╔═══╝ ██║██║  ██║██║╚██╔╝██║██╔══╝  "
echo "  ██║     ██║██████╔╝██║ ╚═╝ ██║███████╗"
echo "  ╚═╝     ╚═╝╚═════╝ ╚═╝     ╚═╝╚══════╝"
echo "  Product Image Discovery & Matching Engine"
echo "  BUAL 5860 · Auburn University"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python
python3 --version > /dev/null 2>&1 || { echo "ERROR: Python 3.10+ is required. See README.md for setup instructions."; exit 1; }

# Install Python deps
echo "→ Installing Python dependencies..."
python3 -m pip install -r requirements.txt -q 2>/dev/null || \
python3 -m pip install -r requirements.txt --break-system-packages -q

# Check if Node.js is available for the frontend
HAS_NODE=false
if command -v node > /dev/null 2>&1; then
    HAS_NODE=true
    echo "→ Installing frontend dependencies..."
    npm install --silent 2>/dev/null || npm install
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  PIDME is starting!"
echo ""
if [ "$HAS_NODE" = true ]; then
echo "  Dashboard:     http://localhost:5173"
fi
echo "  API + Docs:    http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start backend in the background
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Start frontend if Node.js is available
if [ "$HAS_NODE" = true ]; then
    sleep 2
    npx vite --host 0.0.0.0 &
    FRONTEND_PID=$!
fi

# Wait for either to exit; clean up both on Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
