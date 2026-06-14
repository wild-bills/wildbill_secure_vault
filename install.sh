#!/bin/bash
echo "🚀 Setting up local AI Turnkey Factory..."
sudo apt update && sudo apt install -y python3-pip python3-venv

# Set up Python virtual environment
python3 -m venv factory-env
source factory-env/bin/activate
pip install -r requirements.txt

# Verify local Ollama is running
if curl -s http://127.0.0 > /dev/null; then
    echo "✅ Ollama is running locally!"
else
    echo "❌ Warning: Ollama is not detected on port 11434. Please install it."
fi

echo "🎉 Setup complete! Run 'python3 app.py' to launch the web generator."
