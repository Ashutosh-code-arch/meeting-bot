"""
Tests for transcription — meetingbot/transcribe.py and chunk_utils.py

Unit tests:    run without Whisper model loaded (uses mocks or fixture WAV)
Integration:   load real Whisper model
               run with: pytest tests/test_transcribe.py -m slow -v -s
"""

import pytest
import numpy as np
from pathlib import Path

from meetingbot.chunk_utils import merge_chunk_results, extract_all_words


FIXTURE_WAV = Path("tests/fixtures/sample.wav")


# ── Unit tests — chunk_utils.py (no model needed) ─────────────────────────────

def test_merge_empty_chunks():
    """Empty input should return empty segments."""
    result = merge_chunk_results([])
    assert result["segments"] == []


def test_merge_single_chunk_no_offset():
    """Single chunk should have no timestamp offset applied."""
    fake = [{"segments": [
        {"start": 1.0, "end": 5.0, "text": " hello",
         "words": [{"word": "hello", "start": 1.0, "end": 1.5, "probability": 0.99}]}
    ], "language": "hi"}]
    merged = merge_chunk_results(fake)
    assert merged["segments"][0]["start"] == 1.0
    assert merged["segments"][0]["words"][0]["start"] == 1.0


def test_merge_two_chunks_offset():
    """
    Chunk 2 timestamps must be offset by CHUNK_SECONDS (30).
    Segment starting at 1.0s in chunk 2 → 31.0s in merged timeline.
    """
    from meetingbot.config import CHUNK_SECONDS
    seg = {"start": 1.0, "end": 5.0, "text": " hello",
           "words": [{"word": "hello", "start": 1.0, "end": 1.5, "probability": 0.99}]}
    fake = [{"segments": [seg], "language": "hi"},
            {"segments": [seg], "language": "hi"}]
    merged = merge_chunk_results(fake)
    assert len(merged["segments"]) == 2
    assert merged["segments"][0]["start"] == 1.0
    assert merged["segments"][1]["start"] == pytest.approx(1.0 + CHUNK_SECONDS)
    assert merged["segments"][1]["words"][0]["start"] == pytest.approx(1.0 + CHUNK_SECONDS)


def test_merge_three_chunks_offsets():
    """Chunk N timestamps should be offset by N * CHUNK_SECONDS."""
    from meetingbot.config import CHUNK_SECONDS
    seg = {"start": 0.5, "end": 2.0, "text": " hi",
           "words": [{"word": "hi", "start": 0.5, "end": 1.0, "probability": 0.9}]}
    fake = [{"segments": [seg], "language": "hi"} for _ in range(3)]
    merged = merge_chunk_results(fake)
    starts = [s["start"] for s in merged["segments"]]
    assert starts[0] == pytest.approx(0.5)
    assert starts[1] == pytest.approx(0.5 + CHUNK_SECONDS)
    assert starts[2] == pytest.approx(0.5 + 2 * CHUNK_SECONDS)


def test_extract_all_words_sorted():
    """extract_all_words should return a flat list sorted by start time."""
    merged = {"segments": [
        {"start": 5.0, "end": 7.0, "text": " world",
         "words": [{"word": "world", "start": 5.0, "end": 5.5, "probability": 0.9}]},
        {"start": 0.0, "end": 2.0, "text": " hello",
         "words": [{"word": "hello", "start": 0.0, "end": 0.5, "probability": 0.99}]},
    ]}
    words = extract_all_words(merged)
    assert len(words) == 2
    assert words[0]["word"] == "hello"
    assert words[1]["word"] == "world"


def test_language_preserved_in_merge():
    """Language from first chunk should be preserved in merged result."""
    fake = [{"segments": [], "language": "hi"},
            {"segments": [], "language": "en"}]
    merged = merge_chunk_results(fake)
    assert merged["language"] == "hi"


# ── Integration tests — loads real Whisper model ───────────────────────────────

@pytest.mark.slow
@pytest.mark.skipif(not FIXTURE_WAV.exists(), reason="No fixture WAV found at tests/fixtures/sample.wav")
def test_transcribe_returns_segments():
    """Real Whisper call should return at least one segment."""
    from meetingbot.transcribe import load_whisper, transcribe_chunk
    model = load_whisper()
    result = transcribe_chunk(model, FIXTURE_WAV)
    assert "segments" in result
    assert isinstance(result["segments"], list)


@pytest.mark.slow
@pytest.mark.skipif(not FIXTURE_WAV.exists(), reason="No fixture WAV found at tests/fixtures/sample.wav")
def test_word_timestamps_present():
    """Every segment should have a 'words' list with start/end per word."""
    from meetingbot.transcribe import load_whisper, transcribe_chunk
    model = load_whisper()
    result = transcribe_chunk(model, FIXTURE_WAV)
    for seg in result["segments"]:
        assert "words" in seg, f"Segment missing 'words': {seg}"
        for w in seg["words"]:
            assert "start" in w and "end" in w, f"Word missing timestamps: {w}"
            assert w["end"] >= w["start"], f"Word end < start: {w}"
            assert "probability" in w


@pytest.mark.slow
@pytest.mark.skipif(not FIXTURE_WAV.exists(), reason="No fixture WAV found at tests/fixtures/sample.wav")
def test_transcribe_all_chunks_multiple():
    """transcribe_all_chunks on same file twice should produce 2 results."""
    from meetingbot.transcribe import load_whisper, transcribe_all_chunks
    model = load_whisper()
    results = transcribe_all_chunks(model, [FIXTURE_WAV, FIXTURE_WAV])
    assert len(results) == 2
