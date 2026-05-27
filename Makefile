.PHONY: run worker test test-unit test-int check ls report logs lint clean-chunks clean help

VENV = source .venv/bin/activate &&

## Start the menu-bar tray app
run:
	$(VENV) meetingbot

## Start the background worker (open a second terminal for this)
worker:
	$(VENV) meetingbot-worker

## Run all unit tests (no hardware, no ML models needed)
test:
	$(VENV) pytest tests/ -m "not integration and not slow" -v

## Run only the fastest unit tests (merge + transcribe chunk logic)
test-unit:
	$(VENV) pytest tests/test_merge.py tests/test_transcribe.py -v

## Run integration tests (needs BlackHole + mic connected)
test-int:
	$(VENV) pytest tests/ -m integration -v -s

## Check all services are ready before a meeting
check:
	@echo "---- Checking Ollama ----"
	$(VENV) python -c "\
from meetingbot.ollama_client import check_ollama; \
ok = check_ollama(); \
print('Ollama: OK' if ok else 'Ollama: FAIL — run: brew services start ollama')"
	@echo ""
	@echo "---- Checking audio devices ----"
	$(VENV) python -m meetingbot.audio_devices
	@echo ""
	@echo "---- Checking HF_TOKEN ----"
	$(VENV) python -c "\
from dotenv import load_dotenv; import os; load_dotenv(); \
t = os.getenv('HF_TOKEN',''); \
print('HF_TOKEN: OK (' + t[:8] + '...)') if t else print('HF_TOKEN: MISSING — add to .env')"

## List all recorded meetings
ls:
	$(VENV) meetingbot-cli ls

## Open the most recent meeting report in browser
report:
	@open "$$(ls -t ~/meetings/reports/*.html 2>/dev/null | head -1)" \
	|| echo "No reports found in ~/meetings/reports/"

## Tail worker logs live
logs:
	tail -f ~/meetings/worker.log

## Tail tray app logs live
tray-logs:
	tail -f ~/meetings/tray.log

## Lint with ruff
lint:
	$(VENV) ruff check meetingbot/

## Delete raw audio chunks (keeps full WAVs and reports, saves disk space)
clean-chunks:
	rm -f ~/meetings/audio/*_chunk*.wav
	@echo "Audio chunks deleted."

## Full clean — WARNING: deletes ALL meeting data, audio, reports and DB
clean:
	@read -p "Delete ALL meeting data? This cannot be undone. [y/N] " c; \
	[ "$$c" = "y" ] && rm -rf ~/meetings/audio/* ~/meetings/reports/* \
	~/meetings/meetingbot.db ~/meetings/meetingbot.db-wal \
	~/meetings/meetingbot.db-shm && echo "Cleaned." || echo "Cancelled."

## Reinstall package after code changes
install:
	$(VENV) pip install -e ".[dev]"

## Open reports folder in Finder
finder:
	open ~/meetings/reports/

## Show this help
help:
	@echo ""
	@echo "MeetingBot — available commands:"
	@echo ""
	@grep -E '^## ' Makefile | sed 's/## /  make /' | \
	paste - <(grep -E '^[a-zA-Z_-]+:' Makefile | grep -v '^\.PHONY' | \
	awk -F: '{printf "%-18s\n", $$1}') 2>/dev/null || \
	grep -E '^[a-zA-Z_-]+:' Makefile | grep -v '^\.PHONY' | \
	awk -F: '{printf "  make %-18s\n", $$1}'
	@echo ""
