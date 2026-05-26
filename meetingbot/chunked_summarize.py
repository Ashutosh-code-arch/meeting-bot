import logging
from .ollama_client import chat

log = logging.getLogger(__name__)

MAP_SYS = """You are a meeting analyst.
Extract key points, decisions, action items, and speaker contributions
from this PARTIAL transcript section. Be concise. Preserve speaker labels.
Do NOT generate a full report — extract facts only."""


def chunked_summarize(
    user_message: str, final_system: str, chunk_size: int = 45_000, overlap: int = 2_000
) -> str:
    # Separate metadata from transcript body
    sep = "=== MEETING TRANSCRIPT ==="
    if sep in user_message:
        header, body = user_message.split(sep, 1)
        body = body.split("=== END TRANSCRIPT ===")[0]
    else:
        header, body = "", user_message

    # Split into overlapping chunks
    chunks, pos = [], 0
    while pos < len(body):
        chunks.append(body[pos : pos + chunk_size])
        pos += chunk_size - overlap
    log.info(f"Map-reduce: {len(chunks)} chunks")

    # MAP: extract key facts per chunk
    partials = []
    for i, chunk in enumerate(chunks):
        log.info(f"  MAP {i+1}/{len(chunks)}")
        partials.append(chat(MAP_SYS, f"Part {i+1}/{len(chunks)}:\n{chunk}"))

    # REDUCE: combine partials into final 10-section output
    log.info("  REDUCE")
    combined = "\n\n---PART---\n\n".join(
        f"[Part {i+1}]\n{p}" for i, p in enumerate(partials)
    )
    reduce_msg = f"""{header}
NOTE: This is extracted key points from a long meeting split into parts.
Generate the complete 10-section output from these extracted points.

{combined}

Generate full 10-section meeting output now."""
    return chat(final_system, reduce_msg)
