#!/bin/bash
# PIDME startup script — one command to install deps and run the app
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

# Check Python is available
python3 --version > /dev/null 2>&1 || { echo "ERROR: Python 3.10+ is required. See README.md for setup instructions."; exit 1; }

echo "→ Installing dependencies from requirements.txt..."
python3 -m pip install -r requirements.txt -q 2>/dev/null || \
python3 -m pip install -r requirements.txt --break-system-packages -q

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  PIDME is starting!"
echo ""
echo "  API + Swagger UI:  http://localhost:8000/docs"
echo "  Health check:      http://localhost:8000/api/stats"
echo ""
echo "  Press Ctrl+C to stop the server."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
