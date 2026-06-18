# meetingbot/summarize.py
import logging
from pathlib import Path
from .config import PROMPT_PATH, MAX_TRANSCRIPT_CHARS
from .ollama_client import chat, check_ollama

log = logging.getLogger(__name__)


def load_system_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"System prompt not found at {PROMPT_PATH}. "
            "Create prompts/system_prompt.md"
        )
    return PROMPT_PATH.read_text(encoding="utf-8")


def summarize(user_message: str) -> str:
    """
    Send transcript to local LLM. Returns full Markdown report.

    Strategy based on transcript length:
    - Short  (<50k chars, ~35 min): single call, best quality
    - Medium (50k-100k, ~35-70 min): two-pass with key extraction first
    - Long   (>100k, 70+ min): map-reduce chunking
    """
    if not check_ollama():
        raise RuntimeError(
            "Ollama is not running or model not available. "
            "Run: brew services start ollama"
        )

    system = load_system_prompt()
    length = len(user_message)
    log.info(f"Transcript length: {length:,} chars")

    if length <= MAX_TRANSCRIPT_CHARS:
        log.info("Strategy: single-call (fits in context window)")
        return chat(system, user_message)

    elif length <= MAX_TRANSCRIPT_CHARS * 2:
        log.info("Strategy: two-pass (medium meeting ~35-70 min)")
        return _two_pass_summarize(user_message, system)

    else:
        log.info("Strategy: map-reduce (long meeting 70+ min)")
        return _map_reduce_summarize(user_message, system)


def _two_pass_summarize(user_message: str, system: str) -> str:
    """
    For medium-length meetings.
    Pass 1: Extract key facts from full transcript (compresses it).
    Pass 2: Generate full report from the compressed facts.
    This gives much better quality than naive chunking.
    """
    # Split at transcript marker
    sep = "=== MEETING TRANSCRIPT ==="
    end = "=== END TRANSCRIPT ==="
    if sep in user_message:
        header   = user_message.split(sep)[0]
        body     = user_message.split(sep)[1].split(end)[0]
    else:
        header, body = "", user_message

    # Pass 1: compress the transcript into key facts
    log.info("Two-pass: Pass 1 — extracting key facts...")
    extract_prompt = f"""{header}

=== FULL TRANSCRIPT ===
{body}
=== END TRANSCRIPT ===

Extract ALL of the following from this transcript. Be thorough and accurate:

1. DECISIONS: Every decision made, by whom, exact wording
2. ACTION ITEMS: Every task mentioned, owner, deadline if stated
3. KEY DISCUSSION POINTS: Main topics discussed, positions taken
4. QUESTIONS RAISED: Unresolved questions or concerns
5. SPEAKER CONTRIBUTIONS: What each speaker mainly contributed
6. NUMBERS AND DATES: Any specific numbers, dates, deadlines mentioned
7. TECHNICAL DETAILS: Any architecture, tools, features discussed

Preserve speaker labels exactly. Do not invent anything not in the transcript.
If something is unclear, write (unclear). Be exhaustive — missing a fact here means it won't appear in the final report."""

    extracted = chat(
        "You are a meticulous meeting analyst. Extract all facts from the transcript accurately. Never invent information.",
        extract_prompt
    )

    # Pass 2: generate full structured report from extracted facts
    log.info("Two-pass: Pass 2 — generating full report...")
    report_prompt = f"""{header}

NOTE: The transcript was too long to include in full. Below are comprehensively extracted facts from the complete transcript.

=== EXTRACTED MEETING FACTS ===
{extracted}
=== END EXTRACTED FACTS ===

Using these extracted facts, generate the complete 10-section meeting report now.
Only use information from the extracted facts above. Mark anything missing as [MISSING]."""

    return chat(system, report_prompt)


def _map_reduce_summarize(user_message: str, system: str,
                           chunk_size: int = 45_000,
                           overlap: int = 3_000) -> str:
    """
    For long meetings (70+ min).
    MAP: extract key points from each chunk.
    REDUCE: generate final report from all extracted points.
    """
    sep = "=== MEETING TRANSCRIPT ==="
    end = "=== END TRANSCRIPT ==="
    if sep in user_message:
        header = user_message.split(sep)[0]
        body   = user_message.split(sep)[1].split(end)[0]
    else:
        header, body = "", user_message

    # Split into overlapping chunks
    chunks, pos = [], 0
    while pos < len(body):
        chunks.append(body[pos : pos + chunk_size])
        pos += chunk_size - overlap
    log.info(f"Map-reduce: {len(chunks)} chunks")

    MAP_SYS = (
        "You are a meeting analyst. Extract ALL decisions, action items, "
        "key discussion points, and speaker contributions from this transcript section. "
        "Be exhaustive. Preserve exact speaker labels. Never invent information."
    )

    # MAP phase
    partials = []
    for i, chunk in enumerate(chunks):
        log.info(f"  MAP chunk {i+1}/{len(chunks)}...")
        partial = chat(
            MAP_SYS,
            f"Transcript section {i+1} of {len(chunks)}:\n\n{chunk}\n\n"
            f"Extract all decisions, action items, key points, and speaker contributions."
        )
        partials.append(partial)

    # REDUCE phase
    log.info("Map-reduce: REDUCE phase...")
    combined = "\n\n---\n\n".join(
        f"[Section {i+1} of {len(chunks)}]\n{p}"
        for i, p in enumerate(partials)
    )

    reduce_msg = (
        f"{header}\n\n"
        f"NOTE: This is a long meeting. The transcript was processed in {len(chunks)} sections.\n"
        f"Below are extracted facts from each section of the complete transcript.\n\n"
        f"=== EXTRACTED FACTS FROM ALL SECTIONS ===\n"
        f"{combined}\n"
        f"=== END EXTRACTED FACTS ===\n\n"
        f"Generate the complete 10-section meeting report from these facts.\n"
        f"Synthesise across all sections — do not treat them as separate meetings.\n"
        f"Mark anything not mentioned as [MISSING]."
    )
    return chat(system, reduce_msg)
