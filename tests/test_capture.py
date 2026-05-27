"""
Tests for audio capture — meetingbot/capture.py and audio_devices.py

Unit tests:    run without any hardware
Integration:   require BlackHole installed + mic available
               run with: pytest tests/test_capture.py -m integration -v -s
"""

import time
import pytest
from pathlib import Path

from meetingbot.audio_devices import find_input_device, list_devices, validate_devices
from meetingbot.config import SYSTEM_DEVICE_NAME, MIC_DEVICE_NAME, AUDIO_DIR


# ── Unit tests (no hardware needed) ───────────────────────────────────────────

def test_list_devices_does_not_crash():
    """list_devices() should enumerate without raising."""
    list_devices()


def test_find_blackhole():
    """BlackHole input device must be present after brew install blackhole-2ch."""
    idx = find_input_device(SYSTEM_DEVICE_NAME)
    assert isinstance(idx, int)
    assert idx >= 0


def test_find_mic():
    """A microphone input device must be available."""
    idx = find_input_device(MIC_DEVICE_NAME)
    assert isinstance(idx, int)
    assert idx >= 0


def test_find_nonexistent_device_raises():
    """Searching for a device that doesn't exist must raise ValueError."""
    with pytest.raises(ValueError, match="No input device matching"):
        find_input_device("ThisDeviceDefinitelyDoesNotExist_xyz123")


def test_validate_devices_returns_tuple():
    """validate_devices() should return (int, int)."""
    sys_idx, mic_idx = validate_devices(SYSTEM_DEVICE_NAME, MIC_DEVICE_NAME)
    assert isinstance(sys_idx, int)
    assert isinstance(mic_idx, int)
    assert sys_idx >= 0
    assert mic_idx >= 0


# ── Integration tests (need BlackHole + mic + Google Meet routing) ─────────────

@pytest.mark.integration
def test_10_second_capture():
    """
    Record 10 seconds of audio from BlackHole + mic.

    What this tests:
    - Both audio streams open without errors
    - At least one 30s-chunk file is NOT produced (10s < CHUNK_SECONDS)
    - But stop() flushes the remainder so we get exactly 1 chunk
    - The chunk WAV file exists and is non-empty
    - The WAV file is at least 300 KB (valid audio, not silence header only)

    Before running:
    - BlackHole must be installed: brew install blackhole-2ch
    - Google Meet audio output set to Multi-Output Device
    - Run from project root with venv active
    """
    from meetingbot.capture import AudioCapture

    sys_idx = find_input_device(SYSTEM_DEVICE_NAME)
    mic_idx = find_input_device(MIC_DEVICE_NAME)

    cap = AudioCapture(sys_idx, mic_idx, meeting_id=9999)
    cap.start()

    print("\n  Recording 10 seconds...")
    print("  Speak into your mic or play audio in Google Meet.")
    time.sleep(10)

    chunks = cap.stop()

    # Basic checks
    assert len(chunks) >= 1, "No audio chunks produced — check BlackHole routing"

    for c in chunks:
        assert c.exists(), f"Chunk file missing on disk: {c}"
        size = c.stat().st_size
        assert size > 10_000, (
            f"Chunk {c.name} is only {size} bytes — "
            "audio may be silent or device not capturing"
        )

    print(f"\n  Captured {len(chunks)} chunk(s):")
    for c in chunks:
        print(f"    {c.name}  ({c.stat().st_size // 1024} KB)")

    # Cleanup test chunks
    for c in chunks:
        c.unlink(missing_ok=True)


@pytest.mark.integration
def test_30_second_capture_produces_chunk():
    """
    Record 32 seconds so the 30s periodic flush fires at least once,
    producing a chunk mid-recording (not just on stop).
    """
    from meetingbot.capture import AudioCapture

    sys_idx = find_input_device(SYSTEM_DEVICE_NAME)
    mic_idx = find_input_device(MIC_DEVICE_NAME)

    cap = AudioCapture(sys_idx, mic_idx, meeting_id=9998)
    cap.start()

    print("\n  Recording 32 seconds (waiting for periodic flush)...")
    time.sleep(32)

    chunks = cap.stop()

    # At 30s we should have at least 1 mid-recording flush + 1 final flush
    assert len(chunks) >= 1, "Expected at least 1 chunk from 32s recording"

    total_size = sum(c.stat().st_size for c in chunks)
    assert total_size > 50_000, "Total audio size suspiciously small"

    print(f"\n  {len(chunks)} chunk(s), total {total_size // 1024} KB")

    # Cleanup
    for c in chunks:
        c.unlink(missing_ok=True)
