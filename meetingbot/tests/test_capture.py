import time, pytest
from meetingbot.audio_devices import find_input_device, list_devices
from meetingbot.capture import AudioCapture
from meetingbot.config import SYSTEM_DEVICE_NAME, MIC_DEVICE_NAME


def test_list_devices_no_error():
    list_devices()  # should not raise


def test_find_blackhole():
    idx = find_input_device(SYSTEM_DEVICE_NAME)
    assert idx >= 0


def test_find_mic():
    idx = find_input_device(MIC_DEVICE_NAME)
    assert idx >= 0


@pytest.mark.integration
def test_10_second_capture():
    """Integration: record 10 seconds. Needs BlackHole + Google Meet routing."""
    sys_idx = find_input_device(SYSTEM_DEVICE_NAME)
    mic_idx = find_input_device(MIC_DEVICE_NAME)
    cap = AudioCapture(sys_idx, mic_idx, meeting_id=9999)
    cap.start()
    print("\n  Recording 10 seconds...")
    time.sleep(10)
    chunks = cap.stop()
    assert len(chunks) > 0, "No chunks produced"
    for c in chunks:
        assert c.exists(), f"Missing: {c}"
        assert c.stat().st_size > 1000, f"Chunk too small: {c}"
    print(f"  Saved {len(chunks)} chunks")
