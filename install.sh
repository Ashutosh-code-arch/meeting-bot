#!/bin/bash
# install.sh - run once on a fresh Mac
set -euo pipefail

echo "==> Installing system dependencies via Homebrew..."
brew install ffmpeg blackhole-2ch portaudio

echo "==> Installing Ollama..."
brew install ollama
brew services start ollama
sleep 3
ollama pull llama3.1:8b # 4.7GB — fast on M-series, good quality
# For better quality on long meetings: ollama pull llama3.1:70b

echo "==> Creating Python 3.11 virtual environment..."
python3.11 -m venv .venv
source .venv/bin/activate

echo "==> Upgrading pip, setuptools, and wheel first..."
pip install --upgrade pip setuptools wheel

echo "==> Installing meetingbot package and all dependencies..."
pip install -e ".[dev]"

echo "==> Downloading Whisper large-v3 model (~3 GB)..."
echo "    This may take 5-10 minutes depending on your connection..."
python -c "import whisper; whisper.load_model('large-v3')"

echo "==> Creating meeting storage directories..."
mkdir -p ~/meetings/audio
mkdir -p ~/meetings/reports

echo "==> Copying .env template..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    Created .env from .env.example"
else
  echo "    .env already exists, skipping copy"
fi

echo "==> Initialising SQLite database..."
python -c "from meetingbot.db import get_conn; get_conn(); print('    Database ready')"

echo "==> Creating test fixture directory..."
mkdir -p tests/fixtures
touch tests/fixtures/.gitkeep
 
echo ""
echo "========================================="
echo "  Installation complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Add your HuggingFace token to .env"
echo "     Get it at: https://huggingface.co/settings/tokens"
echo "     nano .env"
echo ""
echo "  2. Accept pyannote model terms (all 3 links, one-time):"
echo "     https://huggingface.co/pyannote/speaker-diarization-3.1"
echo "     https://huggingface.co/pyannote/segmentation-3.0"
echo "     https://huggingface.co/pyannote/embedding"
echo ""
echo "  3. Configure BlackHole audio routing:"
echo "     open -a 'Audio MIDI Setup'"
echo "     Create Multi-Output Device: BlackHole 2ch + Built-in Output"
echo "     In Google Meet: Settings > Audio > Output > Multi-Output Device"
echo ""
echo "  4. Verify audio devices:"
echo "     source .venv/bin/activate"
echo "     python -m meetingbot.audio_devices"
echo ""
echo "  5. Start the app:"
echo "     make run      # Terminal 1: menu-bar tray app"
echo "     make worker   # Terminal 2: background processor"
echo ""
