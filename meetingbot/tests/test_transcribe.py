import pytest
from pathlib import Path
from meetingbot.transcribe import load_whisper, transcribe_chunk
from meetingbot.chunk_utils import merge_chunk_results

FIXTURE = Path("tests/fixtures/sample.wav")


@pytest.mark.skipif(not FIXTURE.exists(), reason="No fixture WAV")
def test_word_timestamps_present():
    model = load_whisper()
    result = transcribe_chunk(model, FIXTURE)
    assert "segments" in result and len(result["segments"]) > 0
    for seg in result["segments"]:
        assert "words" in seg
        for w in seg["words"]:
            assert w["end"] >= w["start"]


def test_chunk_offset_logic():
    """Timestamps in chunk 2 should be offset by CHUNK_SECONDS."""
    fake = [
        {
            "segments": [
                {
                    "start": 1.0,
                    "end": 5.0,
                    "text": "hi",
                    "words": [
                        {"word": "hi", "start": 1.0, "end": 1.5, "probability": 0.99}
                    ],
                }
            ]
        }
        for _ in range(3)
    ]
    merged = merge_chunk_results(fake)
    starts = [s["start"] for s in merged["segments"]]
    assert starts[0] == 1.0
    assert starts[1] == 31.0  # 1.0 + 30s offset
    assert starts[2] == 61.0  # 1.0 + 60s offset
