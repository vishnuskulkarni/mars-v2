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
    echo "Created .env with default settings (Ollama mode — free, local)"
fi

# Install Ollama if not already installed
if ! command -v ollama &> /dev/null; then
    echo "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo "Ollama installed"
else
    echo "Ollama already installed"
fi

# Pull the default model
echo "Pulling qwen2.5:7b model (this may take a few minutes on first run)..."
ollama pull qwen2.5:7b

echo ""
echo "Setup complete!"
echo ""
echo "   Default mode: Ollama (free, local)"
echo "   Model: qwen2.5:7b"
echo ""
echo "   To use Claude API instead, edit .env:"
echo "     LLM_PROVIDER=anthropic"
echo "     ANTHROPIC_API_KEY=your-key-here"
echo ""
echo "   Run ./scripts/start.sh to launch MARS."
