#!/bin/bash
# First-time setup — run once
set -e

echo "Setting up MARS..."

# Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
cd ..

# Create .env from template if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "WARNING: Please add your ANTHROPIC_API_KEY to .env"
fi

echo ""
echo "Setup complete! Run ./scripts/start.sh to launch MARS."
