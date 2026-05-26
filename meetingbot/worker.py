import time, logging, traceback, json
from pathlib import Path
from .db import get_conn, claim_job, complete_job, fail_job, get_meeting_result
from .config import AUDIO_DIR

log = logging.getLogger(__name__)
POLL = 5  # seconds between queue polls


def step_transcribe(conn, mid: int) -> dict:
    from .transcribe import load_whisper, transcribe_all_chunks, unload_whisper
    from .chunk_utils import merge_chunk_results

    chunks = sorted(AUDIO_DIR.glob(f"mtg{mid:04d}_chunk*.wav"))
    if not chunks:
        raise FileNotFoundError(f"No chunks for meeting {mid}")
    model = load_whisper()
    results = transcribe_all_chunks(model, chunks)
    merged = merge_chunk_results(results)
    unload_whisper()
    return {"segments": merged["segments"], "chunk_count": len(chunks)}


def step_diarize(conn, mid: int) -> dict:
    from .audio_utils import concat_wav_chunks, get_duration_seconds
    from .diarize import load_diarizer, diarize, unload_diarizer

    chunks = sorted(AUDIO_DIR.glob(f"mtg{mid:04d}_chunk*.wav"))
    full_wav = AUDIO_DIR / f"mtg{mid:04d}_full.wav"
    if not full_wav.exists():
        concat_wav_chunks(chunks, full_wav)
    dur = get_duration_seconds(full_wav)
    pipe = load_diarizer()
    segs = diarize(pipe, full_wav)
    unload_diarizer()
    return {
        "segments": segs,
        "duration_s": dur,
        "speaker_count": len(set(s["speaker"] for s in segs)),
    }


def step_merge(conn, mid: int) -> dict:
    from .merge import assign_speaker_to_words, group_utterances, utterances_to_text

    tx = get_meeting_result(conn, mid, "transcribe")
    di = get_meeting_result(conn, mid, "diarize")
    if not tx or not di:
        raise RuntimeError("Missing transcribe or diarize results")
    labelled = assign_speaker_to_words(tx["segments"], di["segments"])
    utterances = group_utterances(labelled)
    text = utterances_to_text(utterances)
    return {
        "transcript_text": text,
        "utterance_count": len(utterances),
        "duration_min": di["duration_s"] / 60,
    }


def step_summarize(conn, mid: int) -> dict:
    from .summarize import summarize

    mg = get_meeting_result(conn, mid, "merge")
    if not mg:
        raise RuntimeError("Missing merge result")
    row = conn.execute("SELECT title FROM meetings WHERE id=?", (mid,)).fetchone()
    ttl = row["title"] if row else "Meeting"
    msg = (
        f"Meeting title: {ttl}\nDuration: {mg['duration_min']:.0f} min\n\n"
        f"=== MEETING TRANSCRIPT ===\n{mg['transcript_text']}\n=== END TRANSCRIPT ==="
    )
    md = summarize(msg)
    return {"markdown": md, "char_count": len(md)}


def step_export(conn, mid: int) -> dict:
    from .export import export

    sm = get_meeting_result(conn, mid, "summarize")
    if not sm:
        raise RuntimeError("Missing summarize result")
    row = conn.execute("SELECT title FROM meetings WHERE id=?", (mid,)).fetchone()
    ttl = row["title"] if row else "Meeting"
    p = export(sm["markdown"], mid, ttl, auto_open=True)
    conn.execute("UPDATE meetings SET status='done' WHERE id=?", (mid,))
    conn.commit()
    return {"html": str(p["html"]), "md": str(p["markdown"])}


STEPS = {
    "transcribe": step_transcribe,
    "diarize": step_diarize,
    "merge": step_merge,
    "summarize": step_summarize,
    "export": step_export,
}


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s"
    )
    log.info("Worker started. Polling every 5s...")
    conn = get_conn()
    while True:
        worked = False
        for step, handler in STEPS.items():
            job = claim_job(conn, step)
            if not job:
                continue
            jid, mid = job["id"], job["meeting_id"]
            log.info(f"Job {jid}: step={step} meeting={mid}")
            try:
                result = handler(conn, mid)
                complete_job(conn, jid, result)
                log.info(f"Job {jid} done")
            except Exception as e:
                fail_job(conn, jid, f"{type(e).__name__}: {e}")
                log.error(f"Job {jid} failed: {e}")
            worked = True
            break
        if not worked:
            time.sleep(POLL)


if __name__ == "__main__":
    main()
