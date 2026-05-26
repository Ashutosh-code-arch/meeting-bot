from .config import CHUNK_SECONDS


def merge_chunk_results(chunk_results: list[dict]) -> dict:
    """
    Merge Whisper results from multiple 30s chunks into one timeline.
    Offsets all timestamps by chunk_index * CHUNK_SECONDS.
    """
    all_segs = []
    for idx, result in enumerate(chunk_results):
        offset = idx * CHUNK_SECONDS
        for seg in result.get("segments", []):
            all_segs.append(
                {
                    "start": seg["start"] + offset,
                    "end": seg["end"] + offset,
                    "text": seg["text"],
                    "words": [
                        {**w, "start": w["start"] + offset, "end": w["end"] + offset}
                        for w in seg.get("words", [])
                    ],
                }
            )
    lang = chunk_results[0].get("language", "hi") if chunk_results else "hi"
    return {"segments": all_segs, "language": lang}


def extract_all_words(merged: dict) -> list[dict]:
    words = []
    for seg in merged["segments"]:
        words.extend(seg.get("words", []))
    return sorted(words, key=lambda w: w["start"])
