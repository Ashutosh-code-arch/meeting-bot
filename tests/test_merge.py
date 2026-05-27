"""
Tests for merge step — meetingbot/merge.py

All unit tests — no ML models, no hardware needed.
Run with: pytest tests/test_merge.py -v
"""

import pytest
from meetingbot.merge import (
    assign_speaker_to_words,
    group_utterances,
    fmt_ts,
    utterances_to_text,
    Utterance,
)


# ── Shared test fixtures ───────────────────────────────────────────────────────

WORDS_TWO_SPEAKERS = [
    {"word": "hello",   "start": 0.5, "end": 1.0, "probability": 0.99},
    {"word": "team",    "start": 1.1, "end": 1.5, "probability": 0.98},
    {"word": "okay",    "start": 5.0, "end": 5.4, "probability": 0.97},
    {"word": "lets",    "start": 5.5, "end": 5.8, "probability": 0.96},
    {"word": "start",   "start": 5.9, "end": 6.3, "probability": 0.95},
]

DIA_TWO_SPEAKERS = [
    {"speaker": "SPEAKER_00", "start": 0.0, "end": 2.0},
    {"speaker": "SPEAKER_01", "start": 4.5, "end": 7.0},
]

SEGMENTS_TWO_SPEAKERS = [{
    "words": WORDS_TWO_SPEAKERS,
    "start": 0.5, "end": 6.3,
    "text": "hello team okay lets start"
}]


# ── fmt_ts ─────────────────────────────────────────────────────────────────────

def test_fmt_ts_zero():
    assert fmt_ts(0) == "00:00:00"

def test_fmt_ts_seconds_only():
    assert fmt_ts(45) == "00:00:45"

def test_fmt_ts_one_minute():
    assert fmt_ts(60) == "00:01:00"

def test_fmt_ts_one_minute_five():
    assert fmt_ts(65) == "00:01:05"

def test_fmt_ts_one_hour():
    assert fmt_ts(3600) == "01:00:00"

def test_fmt_ts_one_hour_one_minute_one_second():
    assert fmt_ts(3661) == "01:01:01"

def test_fmt_ts_ninety_minutes():
    assert fmt_ts(5400) == "01:30:00"


# ── assign_speaker_to_words ────────────────────────────────────────────────────

def test_first_words_assigned_to_first_speaker():
    labelled = assign_speaker_to_words(SEGMENTS_TWO_SPEAKERS, DIA_TWO_SPEAKERS)
    assert labelled[0]["speaker"] == "SPEAKER_00"
    assert labelled[1]["speaker"] == "SPEAKER_00"

def test_later_words_assigned_to_second_speaker():
    labelled = assign_speaker_to_words(SEGMENTS_TWO_SPEAKERS, DIA_TWO_SPEAKERS)
    assert labelled[2]["speaker"] == "SPEAKER_01"
    assert labelled[3]["speaker"] == "SPEAKER_01"
    assert labelled[4]["speaker"] == "SPEAKER_01"

def test_word_in_gap_gets_unknown():
    """A word that falls in a gap between diarization segments → UNKNOWN."""
    words_in_gap = [{"word": "hmm", "start": 2.5, "end": 3.0, "probability": 0.8}]
    segs = [{"words": words_in_gap, "start": 2.5, "end": 3.0, "text": "hmm"}]
    labelled = assign_speaker_to_words(segs, DIA_TWO_SPEAKERS)
    assert labelled[0]["speaker"] == "UNKNOWN"

def test_empty_words_returns_empty():
    labelled = assign_speaker_to_words([], DIA_TWO_SPEAKERS)
    assert labelled == []

def test_empty_diarization_returns_unknown():
    labelled = assign_speaker_to_words(SEGMENTS_TWO_SPEAKERS, [])
    for w in labelled:
        assert w["speaker"] == "UNKNOWN"

def test_speaker_key_added_to_word():
    """Each returned word dict must have a 'speaker' key added."""
    labelled = assign_speaker_to_words(SEGMENTS_TWO_SPEAKERS, DIA_TWO_SPEAKERS)
    for w in labelled:
        assert "speaker" in w
        assert "word" in w
        assert "start" in w
        assert "end" in w


# ── group_utterances ───────────────────────────────────────────────────────────

def test_two_utterances_from_two_speakers():
    labelled   = assign_speaker_to_words(SEGMENTS_TWO_SPEAKERS, DIA_TWO_SPEAKERS)
    utterances = group_utterances(labelled, gap_threshold=1.5)
    assert len(utterances) == 2

def test_utterance_speakers_correct():
    labelled   = assign_speaker_to_words(SEGMENTS_TWO_SPEAKERS, DIA_TWO_SPEAKERS)
    utterances = group_utterances(labelled, gap_threshold=1.5)
    assert utterances[0].speaker == "SPEAKER_00"
    assert utterances[1].speaker == "SPEAKER_01"

def test_utterance_text_correct():
    labelled   = assign_speaker_to_words(SEGMENTS_TWO_SPEAKERS, DIA_TWO_SPEAKERS)
    utterances = group_utterances(labelled, gap_threshold=1.5)
    assert "hello" in utterances[0].text
    assert "team"  in utterances[0].text
    assert "okay"  in utterances[1].text

def test_utterance_timestamps():
    labelled   = assign_speaker_to_words(SEGMENTS_TWO_SPEAKERS, DIA_TWO_SPEAKERS)
    utterances = group_utterances(labelled, gap_threshold=1.5)
    assert utterances[0].start == pytest.approx(0.5)
    assert utterances[0].end   == pytest.approx(1.5)
    assert utterances[1].start == pytest.approx(5.0)
    assert utterances[1].end   == pytest.approx(6.3)

def test_empty_input_returns_empty():
    utterances = group_utterances([])
    assert utterances == []

def test_single_word_single_utterance():
    words = [{"word": "hello", "start": 0.0, "end": 0.5,
              "probability": 0.99, "speaker": "SPEAKER_00"}]
    utterances = group_utterances(words)
    assert len(utterances) == 1
    assert utterances[0].text == "hello"

def test_large_gap_splits_same_speaker():
    """Same speaker with a gap > threshold should produce 2 utterances."""
    words = [
        {"word": "hello",   "start": 0.0, "end": 0.5, "probability": 0.9, "speaker": "A"},
        {"word": "welcome", "start": 10.0, "end": 10.8, "probability": 0.9, "speaker": "A"},
    ]
    utterances = group_utterances(words, gap_threshold=1.5)
    assert len(utterances) == 2

def test_small_gap_keeps_same_speaker_together():
    """Same speaker with gap < threshold should stay as one utterance."""
    words = [
        {"word": "hello",   "start": 0.0, "end": 0.5, "probability": 0.9, "speaker": "A"},
        {"word": "welcome", "start": 1.0, "end": 1.8, "probability": 0.9, "speaker": "A"},
    ]
    utterances = group_utterances(words, gap_threshold=1.5)
    assert len(utterances) == 1


# ── utterances_to_text ─────────────────────────────────────────────────────────

def test_utterances_to_text_format():
    """Output should be 'SpeakerName [HH:MM:SS]: text' per line."""
    utts = [
        Utterance(speaker="Rahul", start=0.0, end=5.0, text="hello team"),
        Utterance(speaker="Priya", start=6.0, end=10.0, text="haan ready hoon"),
    ]
    text = utterances_to_text(utts)
    lines = text.strip().split("\n")
    assert len(lines) == 2
    assert lines[0] == "Rahul [00:00:00]: hello team"
    assert lines[1] == "Priya [00:00:06]: haan ready hoon"

def test_utterances_to_text_empty():
    text = utterances_to_text([])
    assert text == ""
