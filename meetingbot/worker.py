# meetingbot/worker.py
# Background job processor.
# Run in a separate terminal: make worker
# Polls the SQLite job queue every 5 seconds and processes one step at a time.

import json
import logging
import subprocess
import time
import traceback

from pathlib import Path
from .config import AUDIO_DIR
from .db import (
    claim_job, complete_job, fail_job,
    get_conn, get_meeting_result,
)

log = logging.getLogger(__name__)
POLL_INTERVAL = 5  # seconds between queue polls

# Steps run in this order. Each step depends on the previous one completing.
STEP_ORDER = ["transcribe", "diarize", "merge", "summarize", "export"]


# ── Step handlers ──────────────────────────────────────────────────────────────

def step_transcribe(conn, mid: int) -> dict:
    from .transcribe import load_whisper, transcribe_all_chunks, unload_whisper
    from .chunk_utils import merge_chunk_results

    chunks = sorted(AUDIO_DIR.glob(f"mtg{mid:04d}_chunk*.wav"))
    if not chunks:
        raise FileNotFoundError(
            f"No audio chunks found for meeting {mid} in {AUDIO_DIR}. "
            f"Expected files matching: mtg{mid:04d}_chunk*.wav"
        )

    log.info(f"[transcribe] meeting={mid}, {len(chunks)} chunks")
    model   = load_whisper()
    results = transcribe_all_chunks(model, chunks)
    merged  = merge_chunk_results(results)
    unload_whisper()

    word_count = sum(
        len(seg.get("words", []))
        for seg in merged["segments"]
    )
    return {
        "segments":    merged["segments"],
        "language":    merged.get("language", "hi"),
        "chunk_count": len(chunks),
        "word_count":  word_count,
    }


def step_diarize(conn, mid: int) -> dict:
    from .audio_utils import concat_wav_chunks, get_duration_seconds
    from .diarize import load_diarizer, diarize, unload_diarizer

    chunks   = sorted(AUDIO_DIR.glob(f"mtg{mid:04d}_chunk*.wav"))
    full_wav = AUDIO_DIR / f"mtg{mid:04d}_full.wav"

    if not full_wav.exists():
        if not chunks:
            raise FileNotFoundError(f"No chunks or full WAV for meeting {mid}")
        concat_wav_chunks(chunks, full_wav)

    duration = get_duration_seconds(full_wav)
    log.info(f"[diarize] meeting={mid}, duration={duration:.0f}s")

    pipeline = load_diarizer()
    segs     = diarize(pipeline, full_wav)
    unload_diarizer()

    return {
        "segments":      segs,
        "duration_s":    duration,
        "speaker_count": len(set(s["speaker"] for s in segs)),
    }


def step_merge(conn, mid: int) -> dict:
    from .merge import assign_speaker_to_words, group_utterances, utterances_to_text

    tx = get_meeting_result(conn, mid, "transcribe")
    di = get_meeting_result(conn, mid, "diarize")

    if not tx:
        raise RuntimeError(f"Transcribe result missing for meeting {mid}")
    if not di:
        raise RuntimeError(f"Diarize result missing for meeting {mid}")

    log.info(f"[merge] meeting={mid}")
    labelled   = assign_speaker_to_words(tx["segments"], di["segments"])
    utterances = group_utterances(labelled)
    text       = utterances_to_text(utterances)

    return {
        "transcript_text":  text,
        "utterance_count":  len(utterances),
        "duration_min":     di["duration_s"] / 60,
        "speaker_count":    di["speaker_count"],
    }


def step_summarize(conn, mid: int) -> dict:
    from .summarize import summarize

    mg = get_meeting_result(conn, mid, "merge")
    if not mg:
        raise RuntimeError(f"Merge result missing for meeting {mid}")

    row   = conn.execute("SELECT title FROM meetings WHERE id=?", (mid,)).fetchone()
    title = row["title"] if row else "Meeting"

    log.info(f"[summarize] meeting={mid}, title='{title}', "
             f"{len(mg['transcript_text'])} chars")

    user_msg = (
        f"Meeting title: {title}\n"
        f"Duration: {mg['duration_min']:.0f} minutes\n"
        f"Speakers detected: {mg['speaker_count']}\n"
        f"Total utterances: {mg['utterance_count']}\n\n"
        f"=== MEETING TRANSCRIPT ===\n"
        f"{mg['transcript_text']}\n"
        f"=== END TRANSCRIPT ==="
    )

    markdown = summarize(user_msg)
    return {
        "markdown":   markdown,
        "char_count": len(markdown),
    }


def step_export(conn, mid: int) -> dict:
    from .export import export
    from .audio_utils import cleanup_chunks

    sm = get_meeting_result(conn, mid, "summarize")
    if not sm:
        raise RuntimeError(f"Summarize result missing for meeting {mid}")

    row   = conn.execute("SELECT title, duration_min FROM meetings WHERE id=?", (mid,)).fetchone()
    title = row["title"]       if row else "Meeting"
    dur   = row["duration_min"] if row else 0

    log.info(f"[export] meeting={mid}")
    paths = export(sm["markdown"], mid, title,
                   duration_min=dur or 0, auto_open=True)

    # Mark meeting as done
    conn.execute("UPDATE meetings SET status='done' WHERE id=?", (mid,))
    conn.commit()

    # Clean up raw audio chunks (keep full WAV)
    chunks = sorted(AUDIO_DIR.glob(f"mtg{mid:04d}_chunk*.wav"))
    cleanup_chunks(chunks)

    # macOS notification
    _notify("MeetingBot — Report ready! 🎉",
            f"Meeting #{mid}: {title}",
            f"Saved: {paths['html'].name}")

    return {
        "html_path": str(paths["html"]),
        "md_path":   str(paths["markdown"]),
    }


# ── Step dispatch table ────────────────────────────────────────────────────────

STEP_HANDLERS = {
    "transcribe": step_transcribe,
    "diarize":    step_diarize,
    "merge":      step_merge,
    "summarize":  step_summarize,
    "export":     step_export,
}


# ── Notification helper ────────────────────────────────────────────────────────

def _notify(title: str, subtitle: str, message: str):
    """Send a macOS notification via osascript (no extra deps needed)."""
    try:
        script = (
            f'display notification "{message}" '
            f'with title "{title}" '
            f'subtitle "{subtitle}"'
        )
        subprocess.run(["osascript", "-e", script],
                       capture_output=True, timeout=5)
    except Exception:
        pass  # notifications are best-effort


# ── Main loop ──────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    log.info("Worker started. Polling every 5s for queued jobs...")
    log.info(f"Audio dir: {AUDIO_DIR}")
    conn = get_conn()

    while True:
        processed_any = False

        # Process steps in order so dependencies are always satisfied
        for step in STEP_ORDER:
            job = claim_job(conn, step)
            if job is None:
                continue

            job_id     = job["id"]
            meeting_id = job["meeting_id"]
            handler    = STEP_HANDLERS[step]

            log.info(f"▶ Job {job_id}: step={step} meeting={meeting_id}")
            try:
                result = handler(conn, meeting_id)
                complete_job(conn, job_id, result)
                log.info(f"✓ Job {job_id} ({step}) done")
            except Exception as e:
                error_msg = f"{type(e).__name__}: {e}"
                log.error(f"✗ Job {job_id} ({step}) failed: {error_msg}")
                log.debug(traceback.format_exc())
                fail_job(conn, job_id, error_msg)

            processed_any = True
            break  # Re-poll after each job so we always pick up in step order

        if not processed_any:
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
