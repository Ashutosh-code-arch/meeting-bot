import torch, gc, logging
from pathlib import Path
from pyannote.audio import Pipeline
from .config import HF_TOKEN

log = logging.getLogger(__name__)
_pipeline = None


def load_diarizer():
    global _pipeline
    if _pipeline:
        return _pipeline
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN not set. See .env.example")
    device = (
        torch.device("mps")
        if torch.backends.mps.is_available()
        else torch.device("cpu")
    )
    log.info(f"Loading pyannote speaker-diarization-3.1 on {device}...")
    _pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1", use_auth_token=HF_TOKEN
    ).to(device)
    log.info("pyannote ready")
    return _pipeline


def unload_diarizer():
    global _pipeline
    _pipeline = None
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()


def diarize(
    pipeline,
    audio_path: Path,
    num_speakers: int | None = None,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> list[dict]:
    """
    Run diarization on full meeting WAV.
    Pass num_speakers if exact count known (improves accuracy significantly).
    Returns list of {speaker, start, end} sorted by start time.
    """
    kwargs = {}
    if num_speakers:
        kwargs["num_speakers"] = num_speakers
    elif min_speakers or max_speakers:
        if min_speakers:
            kwargs["min_speakers"] = min_speakers
        if max_speakers:
            kwargs["max_speakers"] = max_speakers

    annotation = pipeline(str(audio_path), **kwargs)
    segments = [
        {"speaker": spk, "start": round(turn.start, 3), "end": round(turn.end, 3)}
        for turn, _, spk in annotation.itertracks(yield_label=True)
    ]
    segments.sort(key=lambda x: x["start"])
    speakers = sorted(set(s["speaker"] for s in segments))
    log.info(f"Diarization: {len(speakers)} speakers, {len(segments)} segments")
    return segments
