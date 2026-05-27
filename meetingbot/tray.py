# meetingbot/tray.py
import logging
import subprocess
import threading

import rumps

from .audio_devices import validate_devices
from .capture import AudioCapture
from .config import HF_TOKEN, MIC_DEVICE_NAME, REPORT_DIR, SYSTEM_DEVICE_NAME
from .db import create_meeting, finish_meeting, get_conn, list_meetings
from .ollama_client import check_ollama

log = logging.getLogger(__name__)


class MeetingBotApp(rumps.App):
    def __init__(self):
        super().__init__("MeetingBot", icon=None, quit_button="Quit MeetingBot")
        self.menu = [
            "▶  Start Recording",
            "⏹  Stop Recording",
            rumps.separator,
            "📂  Open Reports Folder",
            "📋  List Meetings",
            rumps.separator,
            "⚙️  Check Setup",
        ]
        self._capture    = None
        self._meeting_id = None
        self._title      = ""
        self._is_recording = False

    # ── Start recording ────────────────────────────────────────────────────────

    @rumps.clicked("▶  Start Recording")
    def start_rec(self, _):
        if self._is_recording:
            rumps.alert("Already recording!", "Stop the current recording first.")
            return

        resp = rumps.Window(
            message="Meeting title (optional):",
            title="Start Recording",
            default_text="Sprint Planning",
            ok="Start",
            cancel="Cancel"
        ).run()
        if not resp.clicked:
            return

        title = resp.text.strip() or "Untitled Meeting"

        try:
            sys_idx, mic_idx = validate_devices(SYSTEM_DEVICE_NAME, MIC_DEVICE_NAME)
        except ValueError as e:
            rumps.alert("Device Error", str(e))
            return

        conn = get_conn()
        self._meeting_id = create_meeting(conn, str(REPORT_DIR))
        self._title      = title
        self._capture    = AudioCapture(sys_idx, mic_idx, self._meeting_id)
        self._capture.start()
        self._is_recording = True
        self.title = "● REC"

        rumps.notification(
            title="MeetingBot",
            subtitle="Recording started",
            message=f"'{title}' — audio capture is live.",
        )
        log.info(f"Started recording meeting {self._meeting_id}: {title}")

    # ── Stop recording — hands off to WORKER, does NOT run pipeline ───────────

    @rumps.clicked("⏹  Stop Recording")
    def stop_rec(self, _):
        if not self._is_recording:
            rumps.alert("Not recording", "No active recording to stop.")
            return

        # Stop audio capture
        chunk_paths = self._capture.stop()
        meeting_id  = self._meeting_id
        title       = self._title

        self._is_recording = False
        self._capture      = None
        self.title = "MeetingBot"

        # Enqueue all pipeline steps into the job queue.
        # The WORKER process picks these up and runs them.
        # The tray app does NOT call run_pipeline() — that caused the double-load.
        conn = get_conn()
        finish_meeting(conn, meeting_id, title)

        chunk_count = len(chunk_paths)
        log.info(
            f"Stopped recording meeting {meeting_id}: {chunk_count} chunks. "
            f"Jobs enqueued — worker will process."
        )

        rumps.notification(
            title="MeetingBot",
            subtitle="Recording stopped",
            message=(
                f"'{title}' — {chunk_count} chunks saved. "
                f"Worker is processing in the background."
            ),
        )

    # ── Open reports ───────────────────────────────────────────────────────────

    @rumps.clicked("📂  Open Reports Folder")
    def open_reports(self, _):
        subprocess.run(["open", str(REPORT_DIR)])

    # ── List meetings ──────────────────────────────────────────────────────────

    @rumps.clicked("📋  List Meetings")
    def list_mtgs(self, _):
        conn     = get_conn()
        meetings = list_meetings(conn)
        if not meetings:
            rumps.alert("No meetings yet", "Record your first meeting to see it here.")
            return
        lines = []
        for m in meetings[:10]:
            date   = (m["started_at"] or "")[:10]
            status = m["status"] or "unknown"
            title  = m["title"] or "Untitled"
            lines.append(f"#{m['id']:03d}  {date}  {status:<10}  {title}")
        rumps.alert("Recent meetings", "\n".join(lines))

    # ── Setup check ───────────────────────────────────────────────────────────

    @rumps.clicked("⚙️  Check Setup")
    def check_setup(self, _):
        lines = []

        # Audio devices
        try:
            validate_devices(SYSTEM_DEVICE_NAME, MIC_DEVICE_NAME)
            lines.append("✅ Audio: BlackHole + mic found")
        except ValueError as e:
            lines.append(f"❌ Audio: {e}")

        # Ollama
        if check_ollama():
            lines.append("✅ Ollama: running and model ready")
        else:
            lines.append("❌ Ollama: not running — run: brew services start ollama")

        # HuggingFace token
        if HF_TOKEN:
            lines.append(f"✅ HF_TOKEN: set ({HF_TOKEN[:8]}...)")
        else:
            lines.append("❌ HF_TOKEN: missing — add to .env")

        # Worker hint
        lines.append("")
        lines.append("Worker must be running in a separate terminal:")
        lines.append("  make worker")

        rumps.alert("Setup Check", "\n".join(lines))


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    MeetingBotApp().run()
