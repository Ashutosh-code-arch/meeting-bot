from dataclasses import dataclass, field
import bisect, logging

log = logging.getLogger(__name__)


@dataclass
class Utterance:
    speaker: str
    start: float
    end: float
    text: str
    words: list[dict] = field(default_factory=list)


def assign_speaker_to_words(
    whisper_segments: list[dict], dia_segments: list[dict]
) -> list[dict]:
    """
    For each Whisper word, find diarization segment with max overlap.
    Uses word midpoint and binary search for O(n log n) performance.
    """
    dia_starts = [d["start"] for d in dia_segments]
    labelled = []
    unknown = 0
    for seg in whisper_segments:
        for word in seg.get("words", []):
            ws, we = word["start"], word["end"]
            best_spk, best_ov = "UNKNOWN", 0.0
            idx = bisect.bisect_right(dia_starts, we)
            for i in range(max(0, idx - 8), min(len(dia_segments), idx + 4)):
                d = dia_segments[i]
                ov = min(we, d["end"]) - max(ws, d["start"])
                if ov > best_ov:
                    best_ov, best_spk = ov, d["speaker"]
            if best_spk == "UNKNOWN":
                unknown += 1
            labelled.append({**word, "speaker": best_spk})
    if unknown:
        log.warning(f"{unknown} words had no speaker overlap")
    return labelled


def group_utterances(
    labelled_words: list[dict], gap_threshold: float = 1.5
) -> list[Utterance]:
    """
    Group consecutive words by same speaker into utterances.
    New utterance on speaker change or silence gap > threshold.
    """
    if not labelled_words:
        return []
    utterances = []
    cur_spk = labelled_words[0]["speaker"]
    cur_words = [labelled_words[0]]
    for word in labelled_words[1:]:
        gap = word["start"] - cur_words[-1]["end"]
        if word["speaker"] == cur_spk and gap < gap_threshold:
            cur_words.append(word)
        else:
            utterances.append(_make_utt(cur_spk, cur_words))
            cur_spk, cur_words = word["speaker"], [word]
    utterances.append(_make_utt(cur_spk, cur_words))
    log.info(f"Grouped {len(labelled_words)} words into {len(utterances)} utterances")
    return utterances


def _make_utt(speaker, words):
    return Utterance(
        speaker=speaker,
        start=words[0]["start"],
        end=words[-1]["end"],
        text=" ".join(w["word"].strip() for w in words if w["word"].strip()),
        words=words,
    )


def fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def utterances_to_text(utterances: list[Utterance]) -> str:
    return "\n".join(f"{u.speaker} [{fmt_ts(u.start)}]: {u.text}" for u in utterances)
