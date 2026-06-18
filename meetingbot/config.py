# meetingbot/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def _expand(val: str) -> Path:
    """Expand ~ and env vars, then resolve to absolute path."""
    return Path(os.path.expandvars(os.path.expanduser(val))).resolve()

# === Paths ===
BASE_DIR    = _expand(os.getenv("MEETINGBOT_DIR", "~/meetings"))
AUDIO_DIR   = BASE_DIR / "audio"
REPORT_DIR  = BASE_DIR / "reports"
DB_PATH     = BASE_DIR / "meetingbot.db"
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system_prompt.md"
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "report.html.j2"

# Ensure directories exist
for _d in [AUDIO_DIR, REPORT_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# === Audio ===
SAMPLE_RATE        = int(os.getenv("SAMPLE_RATE", "16000"))
CHUNK_SECONDS      = int(os.getenv("CHUNK_SECONDS", "30"))
SYSTEM_DEVICE_NAME = os.getenv("SYSTEM_DEVICE", "BlackHole")
MIC_DEVICE_NAME    = os.getenv("MIC_DEVICE", "MacBook")

# === Whisper ===
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "large-v3")
WHISPER_LANG  = os.getenv("WHISPER_LANG",  "hi")

# === Ollama ===
OLLAMA_MODEL       = os.getenv("OLLAMA_MODEL",       "llama3.1:8b")
OLLAMA_URL         = os.getenv("OLLAMA_URL",         "http://localhost:11434")
OLLAMA_CTX         = int(os.getenv("OLLAMA_CTX",         "32768"))
OLLAMA_MAX_TOKENS  = int(os.getenv("OLLAMA_MAX_TOKENS",  "8192"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.1"))

# === LLM limits ===
MAX_TRANSCRIPT_CHARS = int(os.getenv("MAX_TRANSCRIPT_CHARS", "50000"))

# === HuggingFace ===
HF_TOKEN = os.getenv("HF_TOKEN", "")

# === Speaker name overrides (optional) ===
SPEAKER_NAMES = {
    "SPEAKER_00": os.getenv("SPEAKER_00_NAME", ""),
    "SPEAKER_01": os.getenv("SPEAKER_01_NAME", ""),
    "SPEAKER_02": os.getenv("SPEAKER_02_NAME", ""),
    "SPEAKER_03": os.getenv("SPEAKER_03_NAME", ""),
}
