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

echo "==> Python virtual environment..."
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

echo "==> Downloading Whisper large-v3 model (~3 GB)..."
python -c "import whisper; whisper.load_model('large-v3')"

echo "==> Creating storage directories..."
mkdir -p ~/meetings/{audio,reports}

echo "==> Copying .env template..."
cp .env.example .env

echo "==> Initialising database..."
python -c "from meetingbot.db import get_conn; get_conn()"

echo ""
echo "Installation complete."
echo "Next steps:"
echo "  1. Add HF_TOKEN to .env  (hf.co/settings/tokens)"
echo "  2. Accept pyannote terms  (hf.co/pyannote/speaker-diarization-3.1)"
echo "  3. Audio MIDI Setup: create Multi-Output Device (BlackHole + speakers)"
echo "  4. Set Google Meet audio output to that Multi-Output Device"
echo "  5. Run: meetingbot"
