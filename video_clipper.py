"""Command-line MVP for turning one long video into ranked vertical clips."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field


class Word(BaseModel):
    """A transcript token with its position in the source video."""

    model_config = ConfigDict(extra="ignore")

    word: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)


class Candidate(BaseModel):
    """A transcript-backed moment that is eligible for ranking."""

    id: int
    start_sec: float
    end_sec: float
    transcript: str


class RankedClip(BaseModel):
    start_sec: float
    end_sec: float
    title: str
    score: int = Field(ge=0, le=100)
    reason: str


class RankedClips(BaseModel):
    clips: list[RankedClip]


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True, text=True)


def extract_audio(video: Path, output: Path) -> Path:
    """Extract compact mono audio suitable for the transcription endpoint."""

    _run([
        "ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
        "-b:a", "64k", str(output),
    ])
    return output


def transcribe_with_timestamps(audio: Path, client: OpenAI) -> list[Word]:
    """Transcribe audio using Whisper's word-level timestamps."""

    if audio.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("Extracted audio exceeds 25 MB; split the source before processing")

    with audio.open("rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-1",
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    return [Word.model_validate(word) for word in transcript.words or []]


def _sentences(words: Iterable[Word]) -> list[list[Word]]:
    sentences: list[list[Word]] = []
    current: list[Word] = []
    for word in words:
        current.append(word)
        if word.word.rstrip().endswith((".", "?", "!")):
            sentences.append(current)
            current = []
    if current:
        sentences.append(current)
    return sentences


def create_sentence_windows(
    words: list[Word], min_seconds: float = 25, max_seconds: float = 60
) -> list[Candidate]:
    """Build complete-sentence windows without inventing cut points."""

    if min_seconds <= 0 or max_seconds < min_seconds:
        raise ValueError("Require 0 < min_seconds <= max_seconds")

    sentences = _sentences(words)
    windows: list[Candidate] = []
    for start_index, first in enumerate(sentences):
        for end_index in range(start_index, len(sentences)):
            last = sentences[end_index]
            duration = last[-1].end - first[0].start
            if duration > max_seconds:
                break
            if duration >= min_seconds:
                window_words = [word for sentence in sentences[start_index:end_index + 1] for word in sentence]
                windows.append(Candidate(
                    id=len(windows), start_sec=first[0].start, end_sec=last[-1].end,
                    transcript=" ".join(word.word.strip() for word in window_words),
                ))
    return windows


def rank_with_ai(candidates: list[Candidate], client: OpenAI, count: int = 5) -> list[RankedClip]:
    """Use Structured Outputs to select only transcript-backed candidates."""

    if not candidates:
        return []
    response = client.responses.parse(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": (
                f"Select up to {count} non-overlapping clips. Favor an immediate hook, clarity, "
                "emotional impact, usefulness, self-containedness, and a conclusive ending. "
                "Avoid greetings and ads. Copy start_sec and end_sec exactly from a candidate."
            )},
            {"role": "user", "content": json.dumps([item.model_dump() for item in candidates])},
        ],
        text_format=RankedClips,
    )
    parsed = response.output_parsed
    return parsed.clips if parsed else []


def choose_top_non_overlapping(clips: list[RankedClip], count: int = 5) -> list[RankedClip]:
    """Take highest scoring clips while preventing repeated source material."""

    selected: list[RankedClip] = []
    for clip in sorted(clips, key=lambda item: item.score, reverse=True):
        if all(clip.end_sec <= other.start_sec or clip.start_sec >= other.end_sec for other in selected):
            selected.append(clip)
        if len(selected) == count:
            break
    return sorted(selected, key=lambda item: item.start_sec)


def write_srt(words: list[Word], clip: RankedClip, output: Path, group_size: int = 5) -> Path:
    """Create compact, word-timed caption groups for one clip."""

    included = [word for word in words if word.start >= clip.start_sec and word.end <= clip.end_sec]
    blocks: list[str] = []
    for index in range(0, len(included), group_size):
        group = included[index:index + group_size]
        if not group:
            continue
        start = _srt_time(group[0].start - clip.start_sec)
        end = _srt_time(group[-1].end - clip.start_sec)
        blocks.append(f"{len(blocks) + 1}\n{start} --> {end}\n{' '.join(w.word.strip() for w in group)}")
    output.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return output


def _srt_time(seconds: float) -> str:
    milliseconds = round(max(0, seconds) * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def render_vertical_clip(video: Path, clip: RankedClip, captions: Path, output: Path) -> Path:
    """Render a centered 9:16 clip with captions and normalized audio."""

    escaped_captions = str(captions.resolve()).replace("'", "\\'").replace(":", "\\:")
    filter_graph = (
        "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale=1080:1920,"
        f"subtitles='{escaped_captions}'"
    )
    _run([
        "ffmpeg", "-y", "-ss", str(clip.start_sec), "-to", str(clip.end_sec),
        "-i", str(video), "-vf", filter_graph, "-af", "loudnorm",
        "-c:v", "libx264", "-preset", "medium", "-c:a", "aac", "-movflags", "+faststart",
        str(output),
    ])
    return output


def run_pipeline(video: Path, output_dir: Path, count: int = 5) -> list[Path]:
    """Run transcription, selection, captioning, and rendering for one video."""

    output_dir.mkdir(parents=True, exist_ok=True)
    client = OpenAI()
    with tempfile.TemporaryDirectory(prefix="clipcraft-") as temporary:
        audio = extract_audio(video, Path(temporary) / "audio.mp3")
        words = transcribe_with_timestamps(audio, client)
        candidates = create_sentence_windows(words)
        selected = choose_top_non_overlapping(rank_with_ai(candidates, client, count), count)
        (output_dir / "selection.json").write_text(
            json.dumps([clip.model_dump() for clip in selected], indent=2), encoding="utf-8"
        )
        outputs: list[Path] = []
        for index, clip in enumerate(selected, start=1):
            captions = write_srt(words, clip, output_dir / f"clip-{index}.srt")
            outputs.append(render_vertical_clip(video, clip, captions, output_dir / f"clip-{index}.mp4"))
        return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, help="Source MP4, MOV, or WebM video")
    parser.add_argument("--output", type=Path, default=Path("clips"))
    parser.add_argument("--count", type=int, default=5)
    args = parser.parse_args()
    for output in run_pipeline(args.video, args.output, args.count):
        print(output)


if __name__ == "__main__":
    main()
