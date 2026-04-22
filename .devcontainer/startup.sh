#!/bin/bash
# Codespaces startup script — runs backend + frontend
cd /workspaces/pidme/src

echo "Starting PIDME backend..."
python main.py &
BACKEND_PID=$!

echo "Waiting for backend to be ready..."
for i in {1..15}; do
    if curl -s http://127.0.0.1:8000/api/stats > /dev/null 2>&1; then
        echo "Backend is ready."
        break
    fi
    sleep 1
done

echo "Starting PIDME frontend..."
npx vite --host 0.0.0.0 &
FRONTEND_PID=$!

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  PIDME is running!"
echo ""
echo "  Dashboard:  port 5173 (click Open in Browser)"
echo "  API Docs:   port 8000/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

wait $BACKEND_PID $FRONTEND_PID
