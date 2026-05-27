"""
Tests for the full pipeline — meetingbot/pipeline.py

Uses mocked Ollama so no LLM call is made.
Requires a fixture WAV (auto-created by conftest.py).

Run with: pytest tests/test_pipeline.py -v
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

FIXTURE_WAV = Path("tests/fixtures/sample.wav")

MOCK_MARKDOWN = """# Meeting Output

## 1) Transcript
SPEAKER_00 [00:00:00]: Okay let us start the meeting

## 2) Summary
Short test meeting. Objective: verify pipeline works end to end.

## 3) Speaker-wise Summary
**SPEAKER_00**
- Opened the meeting

## 4) Tasks and Action Items
| Task | Owner | Priority | Due Date | Dependency | Status | Notes |
|------|-------|----------|----------|------------|--------|-------|
| Verify pipeline | SPEAKER_00 | HIGH | [MISSING] | None | Open | Test run |

## 5) Feature-wise Plan
| Feature | Why it matters | Scope | Complexity | Risks | Approach | Owner |
|---------|---------------|-------|-----------|-------|----------|-------|
| Pipeline | Verify system | Small | LOW | None | Run tests | Dev |

## 6) Day-wise Execution Plan
| Day | Goal | Tasks | Output | Risk | Success Criteria |
|-----|------|-------|--------|------|-----------------|
| Day 1 | Test | Run pytest | Green | LOW | All pass |

## 7) Implementation Notes
Test pipeline only. No real meeting content.

## 8) Risks and Constraints
None for this test run.

## 9) References and Learning Links
- pytest documentation — testing — pytest.org

## 10) Final Notes
This is a mock test run. All LLM calls were mocked.
"""


@pytest.mark.skipif(
    not FIXTURE_WAV.exists(),
    reason="Fixture WAV not found. Run conftest.py session fixture first."
)
def test_full_pipeline_with_mock_llm(tmp_path):
    """
    End-to-end pipeline test with mocked Ollama.

    Real steps executed:
    - Whisper transcription (real model)
    - pyannote diarization (real model)
    - Merge (real logic)
    - Export (real HTML generation)

    Mocked:
    - Ollama LLM call → returns MOCK_MARKDOWN above
    - check_ollama → returns True

    This verifies the full pipeline wiring without needing
    a running Ollama server.
    """
    with patch("meetingbot.summarize.chat", return_value=MOCK_MARKDOWN), \
         patch("meetingbot.summarize.check_ollama", return_value=True), \
         patch("meetingbot.config.REPORT_DIR", tmp_path), \
         patch("meetingbot.config.AUDIO_DIR",  tmp_path):

        from meetingbot.pipeline import run_pipeline
        paths = run_pipeline(
            chunk_paths=[FIXTURE_WAV],
            meeting_id=1,
            title="Test Meeting",
            auto_open=False,
        )

    # Both output files must exist
    assert "html" in paths, "No html key in pipeline output"
    assert "markdown" in paths, "No markdown key in pipeline output"
    assert paths["html"].exists(), f"HTML report not created: {paths['html']}"
    assert paths["markdown"].exists(), f"Markdown not created: {paths['markdown']}"

    # HTML must contain the meeting title and key sections
    html = paths["html"].read_text()
    assert "Test Meeting" in html
    assert "Meeting Output" in html
    assert "Transcript" in html

    # Markdown must contain all 10 sections
    md = paths["markdown"].read_text()
    for section in ["1) Transcript", "2) Summary", "3) Speaker",
                    "4) Tasks", "5) Feature", "6) Day",
                    "7) Implementation", "8) Risks", "9) References", "10) Final"]:
        assert section in md, f"Section missing from markdown: {section}"


@pytest.mark.skipif(
    not FIXTURE_WAV.exists(),
    reason="Fixture WAV not found."
)
def test_pipeline_report_files_named_correctly(tmp_path):
    """Report filenames must follow the mtgXXXX_YYYYMMDD_HHMMSS pattern."""
    import re
    with patch("meetingbot.summarize.chat", return_value=MOCK_MARKDOWN), \
         patch("meetingbot.summarize.check_ollama", return_value=True), \
         patch("meetingbot.config.REPORT_DIR", tmp_path), \
         patch("meetingbot.config.AUDIO_DIR",  tmp_path):

        from meetingbot.pipeline import run_pipeline
        paths = run_pipeline(
            chunk_paths=[FIXTURE_WAV],
            meeting_id=42,
            title="Naming Test",
            auto_open=False,
        )

    html_name = paths["html"].name
    md_name   = paths["markdown"].name

    pattern = r"^mtg0042_\d{8}_\d{6}\.(html|md)$"
    assert re.match(pattern, html_name), f"HTML filename wrong: {html_name}"
    assert re.match(pattern.replace("html|md", "md"), md_name), f"MD filename wrong: {md_name}"


def test_pipeline_fails_clearly_when_ollama_down(tmp_path):
    """If Ollama is not running, pipeline should raise RuntimeError, not hang."""
    with patch("meetingbot.summarize.check_ollama", return_value=False), \
         patch("meetingbot.config.REPORT_DIR", tmp_path), \
         patch("meetingbot.config.AUDIO_DIR",  tmp_path):

        from meetingbot.summarize import summarize
        with pytest.raises(RuntimeError, match="Ollama"):
            summarize("test transcript")
