import logging
from pathlib import Path
from .audio_utils import concat_wav_chunks, get_duration_seconds, cleanup_chunks
from .transcribe import load_whisper, transcribe_all_chunks, unload_whisper
from .chunk_utils import merge_chunk_results, extract_all_words
from .diarize import load_diarizer, diarize, unload_diarizer
from .merge import assign_speaker_to_words, group_utterances
from .prompt_builder import build_user_message
from .summarize import summarize
from .export import export
from .config import AUDIO_DIR

log = logging.getLogger(__name__)


def run_pipeline(
    chunk_paths: list[Path],
    meeting_id: int,
    title: str = "Meeting",
    num_speakers: int | None = None,
    participants: list[str] = [],
    auto_open: bool = True,
) -> dict:
    """Full post-meeting pipeline. Returns {'markdown': Path, 'html': Path}."""
    log.info(
        f"=== Pipeline start: meeting {meeting_id} ({len(chunk_paths)} chunks) ==="
    )

    # Step 1: Transcription
    log.info("[1/5] Transcription...")
    model = load_whisper()
    raw = transcribe_all_chunks(model, chunk_paths)
    merged = merge_chunk_results(raw)
    unload_whisper()

    # Step 2: Diarization
    log.info("[2/5] Diarization...")
    full_wav = AUDIO_DIR / f"mtg{meeting_id:04d}_full.wav"
    concat_wav_chunks(chunk_paths, full_wav)
    duration_s = get_duration_seconds(full_wav)
    diarizer = load_diarizer()
    dia_segs = diarize(diarizer, full_wav, num_speakers=num_speakers)
    unload_diarizer()

    # Step 3: Merge
    log.info("[3/5] Merging transcript with speakers...")
    labelled = assign_speaker_to_words(merged["segments"], dia_segs)
    utterances = group_utterances(labelled)
    user_msg = build_user_message(
        utterances,
        meeting_title=title,
        participants=participants,
        duration_min=duration_s / 60,
    )

    # Step 4: Summarize
    log.info("[4/5] LLM summarization...")
    markdown = summarize(user_msg)

    # Step 5: Export
    log.info("[5/5] Exporting report...")
    paths = export(
        markdown, meeting_id, title, duration_min=duration_s / 60, auto_open=auto_open
    )
    cleanup_chunks(chunk_paths)
    log.info(f"=== Done: {paths['html'].name} ===")
    return paths
