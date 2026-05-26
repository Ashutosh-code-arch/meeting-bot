import whisper, torch, gc, logging
from pathlib import Path
from .config import WHISPER_MODEL, WHISPER_LANG

log = logging.getLogger(__name__)
_model = None


def load_whisper():
    global _model
    if _model:
        return _model
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    log.info(f"Loading Whisper {WHISPER_MODEL} on {device}...")
    _model = whisper.load_model(WHISPER_MODEL, device=device)
    return _model


def unload_whisper():
    global _model
    _model = None
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    log.info("Whisper unloaded")


def transcribe_chunk(model, audio_path: Path) -> dict:
    """Transcribe one WAV chunk. Returns Whisper result with word timestamps."""
    result = model.transcribe(
        str(audio_path),
        language=WHISPER_LANG,
        word_timestamps=True,
        task="transcribe",
        verbose=False,
        condition_on_previous_text=True,
        initial_prompt=(
            "This meeting may contain Hindi, English, and Hinglish code-switching. "
            "Technical terms: API, backend, sprint, PR, deploy, CI/CD are common. "
            "Speakers alternate languages mid-sentence."
        ),
        no_speech_threshold=0.6,
        logprob_threshold=-1.0,
        compression_ratio_threshold=2.4,
    )
    log.info(f"  {audio_path.name}: {len(result['segments'])} segments")
    return result


def transcribe_all_chunks(model, chunk_paths: list[Path]) -> list[dict]:
    return [transcribe_chunk(model, p) for p in sorted(chunk_paths)]
