from pathlib import Path

from video_clipper import RankedClip, Word, choose_top_non_overlapping, create_sentence_windows, write_srt


def words_for_sentences(count: int = 10) -> list[Word]:
    words = []
    for index in range(count):
        start = index * 6.0
        words.extend([
            Word(word="Complete", start=start, end=start + 1),
            Word(word="thought.", start=start + 1, end=start + 5),
        ])
    return words


def test_sentence_windows_obey_duration_and_word_boundaries():
    candidates = create_sentence_windows(words_for_sentences(), min_seconds=25, max_seconds=35)

    assert candidates
    assert all(25 <= item.end_sec - item.start_sec <= 35 for item in candidates)
    assert all(item.transcript.startswith("Complete") for item in candidates)
    assert all(item.transcript.endswith("thought.") for item in candidates)


def test_choose_top_non_overlapping_prefers_scores():
    clips = [
        RankedClip(start_sec=0, end_sec=30, title="A", score=70, reason="a"),
        RankedClip(start_sec=10, end_sec=40, title="B", score=95, reason="b"),
        RankedClip(start_sec=45, end_sec=75, title="C", score=80, reason="c"),
    ]

    assert [clip.title for clip in choose_top_non_overlapping(clips)] == ["B", "C"]


def test_write_srt_uses_clip_relative_timestamps(tmp_path: Path):
    clip = RankedClip(start_sec=10, end_sec=20, title="A", score=90, reason="a")
    output = write_srt(
        [Word(word="Hello", start=10.5, end=11), Word(word="world.", start=11, end=12)],
        clip,
        tmp_path / "captions.srt",
    )

    assert "00:00:00,500 --> 00:00:02,000" in output.read_text()
    assert "Hello world." in output.read_text()
