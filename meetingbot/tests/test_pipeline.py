import pytest
from pathlib import Path
from unittest.mock import patch
from meetingbot.pipeline import run_pipeline

FIXTURE = Path("tests/fixtures/sample.wav")
MOCK_MD = "# Meeting Output\n## 1) Transcript\nTest.\n## 2) Summary\nTest summary."


@pytest.mark.skipif(not FIXTURE.exists(), reason="No fixture WAV")
def test_full_pipeline_mock_llm(tmp_path):
    """Full pipeline with mocked Ollama call. Tests all steps except LLM."""
    with (
        patch("meetingbot.summarize.chat", return_value=MOCK_MD),
        patch("meetingbot.summarize.check_ollama", return_value=True),
        patch("meetingbot.config.REPORT_DIR", tmp_path),
        patch("meetingbot.config.AUDIO_DIR", tmp_path),
    ):
        paths = run_pipeline(
            [FIXTURE], meeting_id=1, title="Test Meeting", auto_open=False
        )
    assert paths["html"].exists()
    assert paths["markdown"].exists()
    assert "Test Meeting" in paths["html"].read_text()
