"""
conftest.py — shared pytest fixtures for the meetingbot test suite.

Fixtures here are available to all test files automatically.
No imports needed in test files to use them.
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch


# ── Paths ──────────────────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_WAV   = FIXTURES_DIR / "sample.wav"


# ── Auto-create fixture WAV (runs once per test session) ───────────────────────

@pytest.fixture(scope="session", autouse=True)
def create_sample_wav():
    """
    Auto-creates a 5-second low-noise WAV file at tests/fixtures/sample.wav.

    This is used by transcription and pipeline tests that need real audio
    without requiring a live microphone.

    The audio is low-level noise (not pure silence) to avoid Whisper's
    no_speech suppression filtering it out entirely.
    """
    FIXTURES_DIR.mkdir(exist_ok=True)

    if not SAMPLE_WAV.exists():
        import soundfile as sf
        # 5 seconds of low-level white noise at 16kHz mono
        # Level: 0.001 — audible to Whisper, imperceptible to humans
        duration_s  = 5
        sample_rate = 16000
        rng         = np.random.default_rng(seed=42)  # deterministic
        audio       = rng.standard_normal(sample_rate * duration_s) * 0.001
        sf.write(str(SAMPLE_WAV), audio.astype(np.float32), sample_rate)
        print(f"\n  [conftest] Created fixture WAV: {SAMPLE_WAV}")
    else:
        print(f"\n  [conftest] Fixture WAV already exists: {SAMPLE_WAV}")


# ── Temp database fixture ──────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """
    Creates a fresh SQLite database in a temp directory.
    Patches meetingbot.config paths so nothing touches ~/meetings.

    Usage:
        def test_something(tmp_db):
            conn = tmp_db
            mid = create_meeting(conn, "/tmp/audio")
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("meetingbot.config.DB_PATH",    db_path)
    monkeypatch.setattr("meetingbot.config.AUDIO_DIR",  tmp_path)
    monkeypatch.setattr("meetingbot.config.REPORT_DIR", tmp_path)

    from meetingbot.db import get_conn
    return get_conn()


# ── Mock Whisper model ─────────────────────────────────────────────────────────

@pytest.fixture
def mock_whisper_model():
    """
    A mock Whisper model that returns a deterministic transcript.
    Use when you want to test pipeline logic without loading the real model.

    Usage:
        def test_something(mock_whisper_model):
            result = mock_whisper_model.transcribe("audio.wav", ...)
    """
    model = MagicMock()
    model.transcribe.return_value = {
        "language": "hi",
        "segments": [
            {
                "start": 0.0,
                "end":   5.0,
                "text":  " Okay let us start the sprint planning meeting",
                "words": [
                    {"word": "Okay",     "start": 0.1, "end": 0.5, "probability": 0.99},
                    {"word": "let",      "start": 0.6, "end": 0.8, "probability": 0.98},
                    {"word": "us",       "start": 0.9, "end": 1.0, "probability": 0.97},
                    {"word": "start",    "start": 1.1, "end": 1.4, "probability": 0.99},
                    {"word": "the",      "start": 1.5, "end": 1.6, "probability": 0.98},
                    {"word": "sprint",   "start": 1.7, "end": 2.1, "probability": 0.97},
                    {"word": "planning", "start": 2.2, "end": 2.8, "probability": 0.96},
                    {"word": "meeting",  "start": 2.9, "end": 3.4, "probability": 0.99},
                ],
            },
            {
                "start": 5.5,
                "end":   9.0,
                "text":  " haan main ready hoon",
                "words": [
                    {"word": "haan",  "start": 5.5, "end": 5.8, "probability": 0.95},
                    {"word": "main",  "start": 5.9, "end": 6.1, "probability": 0.94},
                    {"word": "ready", "start": 6.2, "end": 6.6, "probability": 0.96},
                    {"word": "hoon",  "start": 6.7, "end": 7.0, "probability": 0.93},
                ],
            },
        ],
    }
    return model


# ── Mock pyannote diarization pipeline ────────────────────────────────────────

@pytest.fixture
def mock_diarizer():
    """
    A mock pyannote Pipeline that returns a deterministic 2-speaker annotation.
    Use when you want to test pipeline logic without loading the real model.

    SPEAKER_00 speaks from 0–5s, SPEAKER_01 from 5.5–9s.

    Usage:
        def test_something(mock_diarizer):
            result = mock_diarizer("audio.wav")
    """
    try:
        from pyannote.core import Annotation, Segment
        ann = Annotation()
        ann[Segment(0.0, 5.0)]  = "SPEAKER_00"
        ann[Segment(5.5, 9.0)]  = "SPEAKER_01"
        ann[Segment(9.5, 12.0)] = "SPEAKER_00"
        pipe = MagicMock()
        pipe.return_value = ann
        return pipe
    except ImportError:
        pytest.skip("pyannote not installed")


# ── Mock Ollama context manager ────────────────────────────────────────────────

@pytest.fixture
def mock_ollama():
    """
    Patches the Ollama chat call so no real LLM request is made.
    Yields the mock markdown response string.

    Usage:
        def test_something(mock_ollama):
            # Ollama is patched, call summarize() freely
            from meetingbot.summarize import summarize
            result = summarize("some transcript")
            assert "Meeting Output" in result
    """
    mock_response = """# Meeting Output

## 1) Transcript
SPEAKER_00 [00:00:00]: Okay let us start the sprint planning meeting
SPEAKER_01 [00:00:05]: haan main ready hoon

## 2) Summary
Sprint planning meeting. Objective: plan the upcoming sprint.
Key decision: Priya will own backend tasks, SPEAKER_01 will handle testing.

## 3) Speaker-wise Summary
**SPEAKER_00**
- Opened the meeting and set the agenda

**SPEAKER_01**
- Confirmed readiness for the sprint

## 4) Tasks and Action Items
| Task | Owner | Priority | Due Date | Dependency | Status | Notes |
|------|-------|----------|----------|------------|--------|-------|
| Set up sprint board | SPEAKER_00 | HIGH | [MISSING] | None | Open | — |

## 5) Feature-wise Plan
| Feature | Why | Scope | Complexity | Risks | Approach | Owner |
|---------|-----|-------|-----------|-------|----------|-------|
| Sprint planning | Align team | Small | LOW | None | Agile | Team |

## 6) Day-wise Execution Plan
| Day | Goal | Tasks | Output | Risk | Success |
|-----|------|-------|--------|------|---------|
| Day 1 | Start sprint | Create tickets | Jira board | LOW | Board ready |

## 7) Implementation Notes
Standard sprint planning meeting. No technical architecture discussed.

## 8) Risks and Constraints
None identified in this meeting.

## 9) References and Learning Links
- Agile sprint planning guide — process — search by title

## 10) Final Notes
Short meeting. Action item owner for sprint board is assumed to be SPEAKER_00.
"""
    with patch("meetingbot.summarize.chat", return_value=mock_response), \
         patch("meetingbot.summarize.check_ollama", return_value=True):
        yield mock_response
