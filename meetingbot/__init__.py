"""
MeetingBot — local-first meeting intelligence for macOS.

Records Google Meet audio + mic, transcribes with Whisper,
diarizes with pyannote, summarizes with a local LLM (Ollama),
and exports a 10-section dark-theme HTML report.

Zero cloud. Zero data egress. Runs entirely on Mac.
"""

__version__ = "0.1.0"
__author__ = "You"

# Silence noisy third-party loggers at import time
import logging

for noisy in [
    "httpx",
    "httpcore",
    "urllib3",
    "pyannote",
    "pytorch_lightning",
    "speechbrain",
    "asteroid_filterbanks",
]:
    logging.getLogger(noisy).setLevel(logging.WARNING)
