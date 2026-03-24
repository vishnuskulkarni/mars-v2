#!/bin/bash
# Start both backend and frontend
set -e

echo "Launching MARS..."

# Activate venv
source .venv/bin/activate

# Check if using Ollama and start it if needed
if grep -q "LLM_PROVIDER=ollama" .env 2>/dev/null || ! grep -q "LLM_PROVIDER" .env 2>/dev/null; then
    echo "Starting Ollama..."
    ollama serve &>/dev/null &
    OLLAMA_PID=$!
    sleep 2  # Give Ollama a moment to start
    echo "   Ollama running"
fi

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

# Trap Ctrl+C to kill all processes
trap "kill $BACKEND_PID $FRONTEND_PID ${OLLAMA_PID:-} 2>/dev/null; exit" INT TERM
wait
