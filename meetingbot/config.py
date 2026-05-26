from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(os.getenv("MEETINGBOT_DIR", str(Path.home() / "meetings")))
AUDIO_DIR = BASE_DIR / "audio"
REPORT_DIR = BASE_DIR / "reports"
DB_PATH = BASE_DIR / "meetingbot.db"
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system_prompt.md"
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "report.html.j2"

for d in [AUDIO_DIR, REPORT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Audio
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SECONDS = 30

SYSTEM_DEVICE_NAME = os.getenv("SYSTEM_DEVICE", "BlackHole")
MIC_DEVICE_NAME = os.getenv("MIC_DEVICE", "MacBook")

# Models
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "large-v3")
WHISPER_LANG = os.getenv("WHISPER_LANG", "hi")  # hi handles Hinglish best
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
HF_TOKEN = os.getenv("HF_TOKEN", "")

# LLM limits
MAX_TRANSCRIPT_CHARS = 60_000
OLLAMA_CTX = 32768
OLLAMA_MAX_TOKENS = 4096
OLLAMA_TEMPERATURE = 0.1
