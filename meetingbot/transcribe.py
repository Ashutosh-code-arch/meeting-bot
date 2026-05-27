# meetingbot/transcribe.py
import gc
import logging
import numpy as np
import torch
import whisper

from pathlib import Path
from .config import WHISPER_MODEL, WHISPER_LANG

log = logging.getLogger(__name__)
_model = None


# ── MPS float64 patch ──────────────────────────────────────────────────────────
# Whisper's word-timestamp alignment (dtw) calls .double() on a MPS tensor,
# but MPS does not support float64.  We monkey-patch the dtw function to move
# the tensor to CPU first, which is fast (the tensor is tiny at that point).

def _patch_whisper_dtw():
    """Patch whisper.timing.dtw so it runs on CPU, avoiding the MPS float64 error."""
    try:
        import whisper.timing as _timing

        _original_dtw = _timing.dtw

        def _cpu_safe_dtw(x):
            # Move to CPU before the .double() call inside dtw_cpu
            return _original_dtw(x.cpu() if isinstance(x, torch.Tensor) else x)

        _timing.dtw = _cpu_safe_dtw
        log.debug("Whisper dtw patched for MPS float64 compatibility")
    except Exception as e:
        log.warning(f"Could not patch whisper dtw: {e} — word timestamps may fail on MPS")


# Apply patch at import time
_patch_whisper_dtw()


# ── Model loading ──────────────────────────────────────────────────────────────

def load_whisper():
    global _model
    if _model is not None:
        return _model

    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"

    log.info(f"Loading Whisper {WHISPER_MODEL} on {device}...")
    _model = whisper.load_model(WHISPER_MODEL, device=device)
    log.info("Whisper ready")
    return _model


def unload_whisper():
    """Free VRAM/RAM before loading pyannote."""
    global _model
    _model = None
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    log.info("Whisper unloaded")


# ── Transcription ──────────────────────────────────────────────────────────────

def transcribe_chunk(model, audio_path: Path) -> dict:
    """
    Transcribe one 30-second WAV chunk.
    Returns Whisper result dict with word-level timestamps.

    result["segments"][i]["words"] = [
        {"word": str, "start": float, "end": float, "probability": float}
    ]
    """
    result = model.transcribe(
        str(audio_path),
        language=WHISPER_LANG,
        word_timestamps=True,
        task="transcribe",
        verbose=False,
        condition_on_previous_text=True,
        initial_prompt=(
            "This meeting may contain Hindi, English, and Hinglish code-switching. "
            "Technical terms like API, backend, sprint, PR, deploy, CI/CD are common. "
            "Speakers alternate languages mid-sentence."
        ),
        # Suppress hallucinations on silence
        no_speech_threshold=0.6,
        logprob_threshold=-1.0,
        compression_ratio_threshold=2.4,
    )
    seg_count = len(result.get("segments", []))
    lang      = result.get("language", "?")
    log.info(f"  {audio_path.name}: {seg_count} segments, lang={lang}")
    return result


def transcribe_all_chunks(model, chunk_paths: list[Path]) -> list[dict]:
    """Transcribe all chunks in sorted order and return list of results."""
    results = []
    total   = len(chunk_paths)
    for i, path in enumerate(sorted(chunk_paths)):
        log.info(f"Transcribing chunk {i + 1}/{total}: {path.name}")
        results.append(transcribe_chunk(model, path))
    return results
