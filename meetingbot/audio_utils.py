import subprocess, logging
from pathlib import Path
from .config import SAMPLE_RATE

log = logging.getLogger(__name__)


def concat_wav_chunks(chunk_paths: list[Path], out_path: Path) -> Path:
    """Concatenate WAV chunks into single file via ffmpeg. 16kHz mono."""
    list_file = out_path.with_suffix(".list.txt")
    with open(list_file, "w") as f:
        for p in sorted(chunk_paths):
            f.write(f"file '{p.resolve()}'\n")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "-acodec",
            "pcm_s16le",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )
    list_file.unlink(missing_ok=True)
    log.info(f"Concat {len(chunk_paths)} chunks -> {out_path.name}")
    return out_path


def get_duration_seconds(audio_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def cleanup_chunks(chunk_paths: list[Path]):
    """Delete raw chunks after successful pipeline run."""
    for p in chunk_paths:
        p.unlink(missing_ok=True)
    log.info(f"Cleaned up {len(chunk_paths)} audio chunks")
