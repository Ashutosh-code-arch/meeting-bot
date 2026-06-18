# meetingbot/worker.py
# Background job processor.
# Run in a separate terminal: make worker
# Polls the SQLite job queue every 5 seconds.

import json
import logging
import subprocess
import time
import traceback

from pathlib import Path
from .config import AUDIO_DIR, SPEAKER_NAMES
from .db import (
    claim_job, complete_job, fail_job,
    get_conn, get_meeting_result,
)

log = logging.getLogger(__name__)
POLL_INTERVAL = 5
STEP_ORDER    = ["transcribe", "diarize", "merge", "summarize", "export"]


# ── Speaker name helpers ───────────────────────────────────────────────────────

def _build_speaker_map(detected_speakers: list[str]) -> dict[str, str]:
    """
    Build a speaker label -> display name mapping.
    1. Use names from .env (SPEAKER_00_NAME etc.) if set.
    2. Otherwise keep the auto label (SPEAKER_00).
    """
    mapping = {}
    for spk in detected_speakers:
        env_name = SPEAKER_NAMES.get(spk, "").strip()
        mapping[spk] = env_name if env_name else spk
    return mapping


def _apply_speaker_names(transcript_text: str, mapping: dict[str, str]) -> str:
    """Replace SPEAKER_XX labels with real names in transcript text."""
    result = transcript_text
    for label, name in mapping.items():
        if name != label:
            result = result.replace(f"{label} [", f"{name} [")
            result = result.replace(f"{label}:", f"{name}:")
    return result


# ── Step handlers ──────────────────────────────────────────────────────────────

def step_transcribe(conn, mid: int) -> dict:
    from .transcribe import load_whisper, transcribe_all_chunks, unload_whisper
    from .chunk_utils import merge_chunk_results

    chunks = sorted(AUDIO_DIR.glob(f"mtg{mid:04d}_chunk*.wav"))
    if not chunks:
        raise FileNotFoundError(
            f"No audio chunks found for meeting {mid} in {AUDIO_DIR}. "
            f"Expected: mtg{mid:04d}_chunk*.wav"
        )

    log.info(f"[transcribe] meeting={mid}, {len(chunks)} chunks")
    model   = load_whisper()
    results = transcribe_all_chunks(model, chunks)
    merged  = merge_chunk_results(results)
    unload_whisper()

    word_count = sum(len(seg.get("words", [])) for seg in merged["segments"])
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

    if not tx: raise RuntimeError(f"Transcribe result missing for meeting {mid}")
    if not di: raise RuntimeError(f"Diarize result missing for meeting {mid}")

    log.info(f"[merge] meeting={mid}")
    labelled   = assign_speaker_to_words(tx["segments"], di["segments"])
    utterances = group_utterances(labelled)

    # Build speaker map from .env names
    detected  = sorted(set(u.speaker for u in utterances))
    spk_map   = _build_speaker_map(detected)
    log.info(f"  Speaker map: {spk_map}")

    raw_text  = utterances_to_text(utterances)
    named_text = _apply_speaker_names(raw_text, spk_map)

    return {
        "transcript_text":  named_text,
        "speaker_map":      spk_map,
        "utterance_count":  len(utterances),
        "duration_min":     di["duration_s"] / 60,
        "speaker_count":    di["speaker_count"],
    }


def step_summarize(conn, mid: int) -> dict:
    from .summarize import summarize

    mg = get_meeting_result(conn, mid, "merge")
    if not mg: raise RuntimeError(f"Merge result missing for meeting {mid}")

    row   = conn.execute("SELECT title FROM meetings WHERE id=?", (mid,)).fetchone()
    title = row["title"] if row else "Meeting"

    # Build speaker context for the LLM
    spk_map     = mg.get("speaker_map", {})
    speaker_ctx = "\n".join(
        f"  - {label} = {name}" if name != label else f"  - {label} (name unknown)"
        for label, name in spk_map.items()
    )

    log.info(f"[summarize] meeting={mid}, title='{title}', "
             f"{len(mg['transcript_text'])} chars")

    user_msg = (
        f"Meeting title: {title}\n"
        f"Date: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}\n"
        f"Duration: {mg['duration_min']:.0f} minutes\n"
        f"Speakers detected: {mg['speaker_count']}\n"
        f"Speaker labels:\n{speaker_ctx}\n"
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
    if not sm: raise RuntimeError(f"Summarize result missing for meeting {mid}")

    row = conn.execute(
        "SELECT title, duration_min FROM meetings WHERE id=?", (mid,)).fetchone()
    title = row["title"]        if row else "Meeting"
    dur   = row["duration_min"] if row else 0

    log.info(f"[export] meeting={mid}")
    paths = export(sm["markdown"], mid, title,
                   duration_min=dur or 0, auto_open=True)

    conn.execute("UPDATE meetings SET status='done' WHERE id=?", (mid,))
    conn.commit()

    # Clean up raw audio chunks (keep full WAV)
    chunks = sorted(AUDIO_DIR.glob(f"mtg{mid:04d}_chunk*.wav"))
    cleanup_chunks(chunks)

    log.info(f"Report saved: {paths['html']}")
    _notify("MeetingBot — Report ready 🎉",
            f"Meeting: {title}",
            f"Saved to: {paths['html'].name}")

    return {
        "html_path": str(paths["html"]),
        "md_path":   str(paths["markdown"]),
    }


STEP_HANDLERS = {
    "transcribe": step_transcribe,
    "diarize":    step_diarize,
    "merge":      step_merge,
    "summarize":  step_summarize,
    "export":     step_export,
}


def _notify(title: str, subtitle: str, message: str):
    try:
        script = (
            f'display notification "{message}" '
            f'with title "{title}" '
            f'subtitle "{subtitle}"'
        )
        subprocess.run(["osascript", "-e", script],
                       capture_output=True, timeout=5)
    except Exception:
        pass


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    log.info("Worker started. Polling every 5s for queued jobs...")
    log.info(f"Audio dir:   {AUDIO_DIR}")
    log.info(f"Speaker map: {SPEAKER_NAMES}")
    conn = get_conn()

    while True:
        processed_any = False
        for step in STEP_ORDER:
            job = claim_job(conn, step)
            if job is None:
                continue
            job_id, meeting_id = job["id"], job["meeting_id"]
            log.info(f"▶ Job {job_id}: step={step} meeting={meeting_id}")
            try:
                result = STEP_HANDLERS[step](conn, meeting_id)
                complete_job(conn, job_id, result)
                log.info(f"✓ Job {job_id} ({step}) done")
            except Exception as e:
                log.error(f"✗ Job {job_id} ({step}) failed: {type(e).__name__}: {e}")
                log.debug(traceback.format_exc())
                fail_job(conn, job_id, f"{type(e).__name__}: {e}")
            processed_any = True
            break
        if not processed_any:
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
