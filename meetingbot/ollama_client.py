import httpx, json, logging
from typing import Iterator
from .config import (
    OLLAMA_URL,
    OLLAMA_MODEL,
    OLLAMA_CTX,
    OLLAMA_MAX_TOKENS,
    OLLAMA_TEMPERATURE,
)

log = logging.getLogger(__name__)


def check_ollama() -> bool:
    try:
        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in resp.json().get("models", [])]
        if not any(OLLAMA_MODEL in m for m in models):
            log.error(
                f"Model {OLLAMA_MODEL} not found. Run: ollama pull {OLLAMA_MODEL}"
            )
            return False
        return True
    except Exception as e:
        log.error(f"Ollama unreachable: {e}. Start with: brew services start ollama")
        return False


def chat(system: str, user: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {
            "temperature": OLLAMA_TEMPERATURE,
            "num_ctx": OLLAMA_CTX,
            "num_predict": OLLAMA_MAX_TOKENS,
        },
    }
    log.info(f"Calling Ollama: {len(user):,} chars...")
    with httpx.Client(timeout=600.0) as c:
        resp = c.post(f"{OLLAMA_URL}/api/chat", json=payload)
        resp.raise_for_status()
    result = resp.json()["message"]["content"]
    log.info(f"Response: {len(result):,} chars")
    return result


def stream_chat(system: str, user: str) -> Iterator[str]:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "options": {"temperature": OLLAMA_TEMPERATURE, "num_ctx": OLLAMA_CTX},
    }
    with httpx.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload, timeout=600) as r:
        for line in r.iter_lines():
            if line:
                if token := json.loads(line).get("message", {}).get("content"):
                    yield token
