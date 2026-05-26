import logging
from .config import PROMPT_PATH, MAX_TRANSCRIPT_CHARS
from .ollama_client import chat, check_ollama
from .chunked_summarize import chunked_summarize

log = logging.getLogger(__name__)


def load_system_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"System prompt not found at {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")


def summarize(user_message: str) -> str:
    """
    Send transcript to local LLM. Returns full 10-section Markdown.
    Auto-switches to map-reduce if transcript exceeds MAX_TRANSCRIPT_CHARS.
    """
    if not check_ollama():
        raise RuntimeError("Ollama is not running or model unavailable")
    system = load_system_prompt()
    if len(user_message) > MAX_TRANSCRIPT_CHARS:
        log.info(f"Transcript {len(user_message):,} chars — using map-reduce")
        return chunked_summarize(user_message, system)
    return chat(system, user_message)
