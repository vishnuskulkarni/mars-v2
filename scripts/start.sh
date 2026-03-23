#!/bin/bash
# Start both backend and frontend
set -e

echo "Launching MARS..."

# Activate venv
source .venv/bin/activate

# Start backend (background)
uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!

# Start frontend (background)
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "MARS is running!"
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:8000"
echo "   API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop."

# Trap Ctrl+C to kill both processes
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
