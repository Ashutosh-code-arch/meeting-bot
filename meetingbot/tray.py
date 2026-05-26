import rumps, threading, logging, subprocess
from .audio_devices import validate_devices
from .capture import AudioCapture
from .db import get_conn, create_meeting, finish_meeting
from .pipeline import run_pipeline
from .ollama_client import check_ollama
from .config import SYSTEM_DEVICE_NAME, MIC_DEVICE_NAME, REPORT_DIR, HF_TOKEN

log = logging.getLogger(__name__)


class MeetingBotApp(rumps.App):
    def __init__(self):
        super().__init__("MeetingBot", icon=None, quit_button="Quit MeetingBot")
        self.menu = [
            "▶  Start Recording",
            "⏹  Stop and Process",
            rumps.separator,
            "📂  Open Reports Folder",
            "⚙️  Check Setup",
        ]
        self._capture = None
        self._meeting_id = None
        self._title = ""
        self._is_recording = False

    @rumps.clicked("▶  Start Recording")
    def start_rec(self, _):
        if self._is_recording:
            rumps.alert("Already recording!", "Stop the current recording first.")
            return
        resp = rumps.Window(
            message="Meeting title:",
            title="Start Recording",
            default_text="Sprint Planning",
            ok="Start",
            cancel="Cancel",
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
        self._meeting_id = create_meeting(conn, "")
        self._title = title
        self._capture = AudioCapture(sys_idx, mic_idx, self._meeting_id)
        self._capture.start()
        self._is_recording = True
        self.title = "● REC"
        rumps.notification("MeetingBot", "Recording started", f"'{title}' is live.")

    @rumps.clicked("⏹  Stop and Process")
    def stop_rec(self, _):
        if not self._is_recording:
            rumps.alert("Not recording")
            return
        chunks = self._capture.stop()
        mid, title = self._meeting_id, self._title
        self._is_recording = False
        self.title = "⏳ Processing..."
        conn = get_conn()
        finish_meeting(conn, mid, title)

        def _process():
            try:
                paths = run_pipeline(chunks, mid, title)
                rumps.notification("MeetingBot", "Report ready!", paths["html"].name)
            except Exception as e:
                rumps.notification("MeetingBot", "Error", str(e)[:120])
                log.error(f"Pipeline error: {e}", exc_info=True)
            finally:
                self.title = "MeetingBot"

        threading.Thread(target=_process, daemon=True).start()

    @rumps.clicked("📂  Open Reports Folder")
    def open_reports(self, _):
        subprocess.run(["open", str(REPORT_DIR)])

    @rumps.clicked("⚙️  Check Setup")
    def check_setup(self, _):
        lines = []
        try:
            validate_devices(SYSTEM_DEVICE_NAME, MIC_DEVICE_NAME)
            lines.append("✅ Audio devices: BlackHole + mic found")
        except ValueError as e:
            lines.append(f"❌ Audio: {e}")
        lines.append(
            "✅ Ollama: ready"
            if check_ollama()
            else "❌ Ollama: not running or model missing"
        )
        lines.append("✅ HF_TOKEN: set" if HF_TOKEN else "❌ HF_TOKEN: not set in .env")
        rumps.alert("Setup Check", "\n".join(lines))


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    MeetingBotApp().run()
