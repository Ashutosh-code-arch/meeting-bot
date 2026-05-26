import threading, logging
import numpy as np
import sounddevice as sd
import soundfile as sf
from pathlib import Path
from .config import SAMPLE_RATE, CHUNK_SECONDS, AUDIO_DIR

log = logging.getLogger(__name__)


class AudioCapture:
    """
    Records two InputStream simultaneously:
      system_device: BlackHole 2ch (Google Meet remote audio)
      mic_device:    Built-in mic  (your voice)
    Mixes to mono, writes 30-second WAV chunks to AUDIO_DIR.
    """

    def __init__(self, system_device: int, mic_device: int, meeting_id: int):
        self.system_device = system_device
        self.mic_device = mic_device
        self.meeting_id = meeting_id
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._buf_sys: list = []
        self._buf_mic: list = []
        self._chunks: list[Path] = []
        self._chunk_idx = 0

    def _sys_cb(self, indata, frames, time_info, status):
        if status:
            log.warning(f"[system] {status}")
        with self._lock:
            self._buf_sys.append(indata.copy())

    def _mic_cb(self, indata, frames, time_info, status):
        if status:
            log.warning(f"[mic] {status}")
        with self._lock:
            self._buf_mic.append(indata.copy())

    def _flush(self):
        with self._lock:
            sys_buf, mic_buf = self._buf_sys[:], self._buf_mic[:]
            self._buf_sys.clear()
            self._buf_mic.clear()
        if not sys_buf and not mic_buf:
            return
        sys_arr = np.concatenate(sys_buf, axis=0) if sys_buf else np.zeros((1, 2))
        mic_arr = np.concatenate(mic_buf, axis=0) if mic_buf else np.zeros((1, 1))
        n = min(len(sys_arr), len(mic_arr))
        sys_mono = sys_arr[:n].mean(axis=1)
        mic_mono = mic_arr[:n, 0]
        mixed = np.clip((sys_mono + mic_mono) * 0.5, -1.0, 1.0)
        out = AUDIO_DIR / f"mtg{self.meeting_id:04d}_chunk{self._chunk_idx:04d}.wav"
        sf.write(str(out), mixed.astype(np.float32), SAMPLE_RATE, subtype="PCM_16")
        self._chunks.append(out)
        self._chunk_idx += 1
        log.info(f"Flushed chunk {self._chunk_idx} -> {out.name}")

    def start(self):
        self._stop.clear()
        self._sys_stream = sd.InputStream(
            device=self.system_device,
            samplerate=SAMPLE_RATE,
            channels=2,
            dtype="float32",
            callback=self._sys_cb,
            blocksize=1024,
        )
        self._mic_stream = sd.InputStream(
            device=self.mic_device,
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=self._mic_cb,
            blocksize=1024,
        )
        self._sys_stream.start()
        self._mic_stream.start()

        def _flush_loop():
            while not self._stop.wait(CHUNK_SECONDS):
                self._flush()

        threading.Thread(target=_flush_loop, daemon=True).start()
        log.info(f"Recording started: meeting {self.meeting_id}")

    def stop(self) -> list[Path]:
        self._stop.set()
        self._sys_stream.stop()
        self._mic_stream.stop()
        self._flush()
        log.info(f"Stopped. {len(self._chunks)} chunks saved.")
        return self._chunks
