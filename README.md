# MeetingBot

A fully local, zero-cloud meeting intelligence system for macOS.

Records Google Meet audio + your microphone, then automatically:

- Transcribes with **Whisper large-v3** (Apple Silicon MPS accelerated)
- Diarizes speakers with **pyannote 3.1**
- Summarizes with a **local LLM via Ollama** (llama3.1:8b)
- Exports a **10-section dark-theme HTML report**

**Supports Hindi, English, and Hinglish code-switching.**
**Zero data leaves your Mac.**

---

## Quick start (Day 1)

### Prerequisites

- macOS 13+ (Ventura or Sonoma)
- Apple Silicon or Intel Mac with 16 GB RAM recommended
- Python 3.11+
- Homebrew

### Install

```bash
git clone https://github.com/yourname/meetingbot
cd meetingbot
bash install.sh
```

### Configure (one-time)

```bash
# 1. Edit .env — add your HuggingFace token
nano .env

# 2. Accept pyannote model terms (one-time browser step)
open https://hf.co/pyannote/speaker-diarization-3.1

# 3. Audio MIDI Setup — route Meet audio through BlackHole
open -a "Audio MIDI Setup"
# Press (+) → Create Multi-Output Device
# Check: BlackHole 2ch + Built-in Output
# In Google Meet: Settings → Audio → Output → Multi-Output Device
```

### Run

```bash
# Terminal 1: start the tray app (or use launchd for auto-start)
make run

# Terminal 2: start the background worker
make worker
```

Then in the menu bar: click **MeetingBot → Start Recording** before your Meet call.
Click **Stop and Process** when the meeting ends.
A browser window opens automatically with the report.

---

## Development

```bash
make test        # unit tests (no hardware needed)
make test-int    # integration tests (needs BlackHole + Ollama)
make lint        # ruff linting
make check       # verify Ollama + audio devices are ready
make ls          # list all recorded meetings
make logs        # tail worker logs live
```

---

## Project structure

```
meetingbot/
├── meetingbot/       Python package (all pipeline code)
├── prompts/          LLM system prompt (edit to customise output)
├── templates/        HTML report Jinja2 template
├── tests/            pytest test suite
├── install.sh        One-time setup script
├── install_launchd.sh Auto-start on login setup
├── Makefile          Common dev commands
└── .env              Your secrets (HF_TOKEN etc.)
```

---

## Configuration

All settings in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `HF_TOKEN` | (required) | HuggingFace token for pyannote |
| `WHISPER_MODEL` | `large-v3` | Use `medium` if RAM limited |
| `WHISPER_LANG` | `hi` | `hi` handles Hinglish best |
| `OLLAMA_MODEL` | `llama3.1:8b` | Use `70b` for better quality |
| `SYSTEM_DEVICE` | `BlackHole` | Virtual audio device name |
| `MIC_DEVICE` | `MacBook` | Your mic device name fragment |
| `MEETINGBOT_DIR` | `~/meetings` | Storage directory |

---

## Output

Each meeting produces:

- `~/meetings/reports/mtgXXXX_YYYYMMDD.html` — dark-theme browser report
- `~/meetings/reports/mtgXXXX_YYYYMMDD.md`  — raw Markdown

Report sections: Transcript · Summary · Speaker-wise Summary ·
Tasks Table · Feature Plan · Day-wise Plan · Implementation Notes ·
Risks · References · Final Notes

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| BlackHole not capturing Meet | Set Meet audio output to Multi-Output Device in Meet settings |
| `HF_TOKEN` error | Accept model terms at hf.co/pyannote/speaker-diarization-3.1 |
| Ollama not responding | Run: `brew services start ollama` |
| MPS not available | Check: `python -c "import torch; print(torch.backends.mps.is_available())"` |
| Mic permission denied | System Settings → Privacy → Microphone → allow Terminal |
| Out of memory | Switch to `WHISPER_MODEL=medium` in .env |
| Worker not processing | Check: `tail -f ~/meetings/worker.log` |

---

## Roadmap

- **Phase 1** (this repo): Local Mac app — one user, one machine
- **Phase 2**: Self-hosted Docker service — multi-user, REST API
- **Phase 3**: Desktop client + encrypted cloud sync
