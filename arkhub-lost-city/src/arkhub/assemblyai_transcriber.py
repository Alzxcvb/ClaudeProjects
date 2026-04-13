from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import assemblyai as aai


@dataclass
class TranscriptWord:
    text: str
    start_seconds: float
    end_seconds: float
    confidence: float


@dataclass
class TranscriptResult:
    video_id: str
    full_text: str
    words: list[TranscriptWord]
    audio_duration_seconds: float
    language_code: str


def _resolve_api_key(api_key: str | None) -> str:
    key = api_key or os.environ.get("ASSEMBLYAI_API_KEY")
    if not key:
        raise RuntimeError(
            "AssemblyAI API key not provided. Pass api_key= or set ASSEMBLYAI_API_KEY."
        )
    return key


def transcribe_audio(
    mp3_path: Path, video_id: str, api_key: str | None = None
) -> TranscriptResult:
    """Transcribe an MP3 file via AssemblyAI. Returns word-level timestamps.

    If api_key is None, reads ASSEMBLYAI_API_KEY from env. Raises RuntimeError if neither is set.
    """
    aai.settings.api_key = _resolve_api_key(api_key)

    if not mp3_path.exists():
        raise RuntimeError(f"[{video_id}] MP3 file not found: {mp3_path}")

    config = aai.TranscriptionConfig(
        speech_model=aai.SpeechModel.best,
        punctuate=True,
        format_text=True,
    )

    try:
        transcript = aai.Transcriber().transcribe(str(mp3_path), config=config)
    except Exception as exc:
        raise RuntimeError(f"[{video_id}] AssemblyAI request failed: {exc}") from exc

    if getattr(transcript, "status", None) == aai.TranscriptStatus.error:
        raise RuntimeError(f"[{video_id}] Transcription error: {transcript.error}")

    words: list[TranscriptWord] = []
    for w in transcript.words or []:
        words.append(
            TranscriptWord(
                text=w.text,
                start_seconds=float(w.start) / 1000.0,
                end_seconds=float(w.end) / 1000.0,
                confidence=float(w.confidence),
            )
        )

    duration = float(getattr(transcript, "audio_duration", 0.0) or 0.0)
    language = getattr(transcript, "language_code", None) or "en"

    return TranscriptResult(
        video_id=video_id,
        full_text=transcript.text or "",
        words=words,
        audio_duration_seconds=duration,
        language_code=language,
    )


def save_transcript(result: TranscriptResult, out_path: Path) -> None:
    """Serialize TranscriptResult as JSON to out_path. Create parent dirs."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(asdict(result), f, indent=2)


def load_transcript(path: Path) -> TranscriptResult:
    """Load TranscriptResult from a JSON file previously saved by save_transcript."""
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    words = [TranscriptWord(**w) for w in data.get("words", [])]
    return TranscriptResult(
        video_id=data["video_id"],
        full_text=data["full_text"],
        words=words,
        audio_duration_seconds=float(data["audio_duration_seconds"]),
        language_code=data["language_code"],
    )


def batch_transcribe(
    mp3_paths: list[tuple[str, Path]],
    out_dir: Path,
    api_key: str | None = None,
    skip_existing: bool = True,
) -> list[TranscriptResult]:
    """Transcribe multiple MP3s. Writes each to out_dir / f"{video_id}.json".

    If skip_existing=True and the JSON already exists, load and return it instead of
    re-transcribing. Returns list of TranscriptResult in input order.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(mp3_paths)
    results: list[TranscriptResult] = []

    for i, (video_id, mp3_path) in enumerate(mp3_paths, start=1):
        out_path = out_dir / f"{video_id}.json"
        if skip_existing and out_path.exists():
            print(f"[{i}/{total}] {video_id}: cached, loading...")
            results.append(load_transcript(out_path))
            continue

        print(f"[{i}/{total}] {video_id}: transcribing...")
        try:
            result = transcribe_audio(mp3_path, video_id, api_key=api_key)
            save_transcript(result, out_path)
            print(f"\u2713 {len(result.words)} words")
            results.append(result)
        except Exception as exc:
            print(f"\u2717 {exc}")
            raise

    return results
