from meetingbot.merge import assign_speaker_to_words, group_utterances, fmt_ts

WORDS = [
    {"word": "hello", "start": 0.5, "end": 1.0, "probability": 0.99},
    {"word": "team", "start": 1.1, "end": 1.5, "probability": 0.98},
    {"word": "okay", "start": 5.0, "end": 5.4, "probability": 0.97},
    {"word": "lets", "start": 5.5, "end": 5.8, "probability": 0.96},
    {"word": "go", "start": 5.9, "end": 6.2, "probability": 0.95},
]
DIA = [
    {"speaker": "SPEAKER_00", "start": 0.0, "end": 2.0},
    {"speaker": "SPEAKER_01", "start": 4.5, "end": 7.0},
]
SEGS = [{"words": WORDS, "start": 0.5, "end": 6.2, "text": "hello team okay lets go"}]


def test_speaker_assignment():
    labelled = assign_speaker_to_words(SEGS, DIA)
    assert labelled[0]["speaker"] == "SPEAKER_00"
    assert labelled[2]["speaker"] == "SPEAKER_01"


def test_utterance_grouping():
    labelled = assign_speaker_to_words(SEGS, DIA)
    utterances = group_utterances(labelled, gap_threshold=1.5)
    assert len(utterances) == 2
    assert utterances[0].speaker == "SPEAKER_00"
    assert utterances[1].speaker == "SPEAKER_01"
    assert "hello" in utterances[0].text


def test_fmt_ts():
    assert fmt_ts(0) == "00:00:00"
    assert fmt_ts(65) == "00:01:05"
    assert fmt_ts(3661) == "01:01:01"


def test_empty_input():
    assert group_utterances([]) == []
