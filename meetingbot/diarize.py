# meetingbot/diarize.py
import gc
import logging
import torch

from pathlib import Path
from .config import HF_TOKEN

log = logging.getLogger(__name__)
_pipeline = None


def load_diarizer():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN not set. Add it to .env")

    device = (
        torch.device("mps")  if torch.backends.mps.is_available() else
        torch.device("cuda") if torch.cuda.is_available() else
        torch.device("cpu")
    )
    log.info(f"Loading pyannote speaker-diarization-3.1 on {device}...")

    from pyannote.audio import Pipeline
    _pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=HF_TOKEN
    ).to(device)

    log.info("pyannote ready")
    return _pipeline


def unload_diarizer():
    global _pipeline
    _pipeline = None
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    log.info("pyannote unloaded")


def diarize(pipeline, audio_path: Path,
            num_speakers: int | None = None,
            min_speakers: int | None = None,
            max_speakers: int | None = None) -> list[dict]:
    """
    Run speaker diarization on the full meeting WAV.
    Returns list of {speaker, start, end} dicts sorted by start time.
    """
    kwargs = {}
    if num_speakers:
        kwargs["num_speakers"] = num_speakers
    elif min_speakers or max_speakers:
        if min_speakers: kwargs["min_speakers"] = min_speakers
        if max_speakers: kwargs["max_speakers"] = max_speakers

    log.info(f"Running diarization on {audio_path.name} {kwargs}...")
    output = pipeline(str(audio_path), **kwargs)

    log.debug(f"pyannote output type: {type(output)}")
    log.debug(f"pyannote output attrs: {[a for a in dir(output) if not a.startswith('_')]}")

    segments = _extract_segments(output)
    segments.sort(key=lambda x: x["start"])

    speakers = sorted(set(s["speaker"] for s in segments))
    log.info(f"Diarization done: {len(speakers)} speakers, {len(segments)} segments")
    log.info(f"  Speakers: {speakers}")
    return segments


def _extract_segments(output) -> list[dict]:
    """
    Extract speaker segments from pyannote output.

    pyannote.audio 3.x returns a DiarizeOutput object.
    Based on the actual attributes seen at runtime:
      - exclusive_speaker_diarization
      - speaker_diarization        <-- this is the Annotation we want
      - speaker_embeddings
      - serialize
    """
    segments = []

    # ── Strategy 1: DiarizeOutput.speaker_diarization (pyannote 3.x) ─────────
    # This is the actual annotation object inside DiarizeOutput
    if hasattr(output, "speaker_diarization"):
        annotation = output.speaker_diarization
        log.debug(f"Using speaker_diarization attr, type: {type(annotation)}")
        for turn, _, speaker in annotation.itertracks(yield_label=True):
            segments.append({
                "speaker": str(speaker),
                "start":   round(turn.start, 3),
                "end":     round(turn.end,   3),
            })
        return segments

    # ── Strategy 2: exclusive_speaker_diarization ─────────────────────────────
    if hasattr(output, "exclusive_speaker_diarization"):
        annotation = output.exclusive_speaker_diarization
        log.debug(f"Using exclusive_speaker_diarization attr, type: {type(annotation)}")
        for turn, _, speaker in annotation.itertracks(yield_label=True):
            segments.append({
                "speaker": str(speaker),
                "start":   round(turn.start, 3),
                "end":     round(turn.end,   3),
            })
        return segments

    # ── Strategy 3: to_annotation() method ───────────────────────────────────
    if hasattr(output, "to_annotation"):
        annotation = output.to_annotation()
        for turn, _, speaker in annotation.itertracks(yield_label=True):
            segments.append({
                "speaker": str(speaker),
                "start":   round(turn.start, 3),
                "end":     round(turn.end,   3),
            })
        return segments

    # ── Strategy 4: direct itertracks (old pyannote Annotation) ──────────────
    if hasattr(output, "itertracks"):
        for turn, _, speaker in output.itertracks(yield_label=True):
            segments.append({
                "speaker": str(speaker),
                "start":   round(turn.start, 3),
                "end":     round(turn.end,   3),
            })
        return segments

    # ── Strategy 5: serialize() returns a dict ────────────────────────────────
    if hasattr(output, "serialize"):
        try:
            import json
            data = json.loads(output.serialize())
            log.debug(f"Serialized output keys: {list(data.keys())}")
            # Try to find annotation data in serialized form
            for key in ["speaker_diarization", "annotation", "diarization"]:
                if key in data:
                    from pyannote.core import Annotation
                    ann = Annotation.from_json(data[key])
                    for turn, _, speaker in ann.itertracks(yield_label=True):
                        segments.append({
                            "speaker": str(speaker),
                            "start":   round(turn.start, 3),
                            "end":     round(turn.end,   3),
                        })
                    if segments:
                        return segments
        except Exception as e:
            log.debug(f"serialize() strategy failed: {e}")

    # ── Strategy 6: iterate the object directly ───────────────────────────────
    try:
        for item in output:
            if len(item) == 3:
                turn, _, speaker = item
            elif len(item) == 2:
                turn, speaker = item
            else:
                continue
            segments.append({
                "speaker": str(speaker),
                "start":   round(float(turn.start), 3),
                "end":     round(float(turn.end),   3),
            })
        if segments:
            return segments
    except (TypeError, ValueError):
        pass

    raise RuntimeError(
        f"Cannot extract segments from pyannote output type: {type(output)}.\n"
        f"Attributes: {[a for a in dir(output) if not a.startswith('_')]}\n"
        f"Please report this — run: python3 -c \""
        f"from pyannote.audio import Pipeline; "
        f"print(Pipeline.__module__)\" to get the version."
    )
