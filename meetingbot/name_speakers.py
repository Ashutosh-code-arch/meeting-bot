import json
from pathlib import Path


def prompt_speaker_names(speaker_ids: list[str]) -> dict[str, str]:
    """CLI: rename SPEAKER_00 to real names. Press Enter to keep auto-label."""
    mapping = {}
    print("\n-- Speaker labelling ----------------")
    print("  Press Enter to keep the auto-label.")
    for sid in speaker_ids:
        name = input(f"  {sid} -> real name (or Enter): ").strip()
        mapping[sid] = name if name else sid
    return mapping


def apply_names(segments: list[dict], mapping: dict) -> list[dict]:
    return [{**s, "speaker": mapping.get(s["speaker"], s["speaker"])} for s in segments]


def save_speaker_map(mapping: dict, path: Path):
    path.write_text(json.dumps(mapping, indent=2))


def load_speaker_map(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}
