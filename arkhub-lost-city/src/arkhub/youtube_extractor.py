from __future__ import annotations

import csv
import http.cookiejar
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import scrapetube


@dataclass
class YouTubeConfig:
    channel_handle: str          # e.g. "@PillarsofthePast101"
    max_videos: int = 0          # 0 = fetch all
    output_prefix: str = "youtube"
    language: str = "en"
    cookies_file: str | None = None  # Path to Netscape-format cookies.txt (export from browser)


def slugify(value: str) -> str:
    """Create a safe filesystem slug from a string."""
    import re
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return text or "youtube"


def ensure_parent(path: Path) -> None:
    """Create parent directory if it doesn't exist."""
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    """Write a JSON file to disk."""
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write rows to a CSV file."""
    ensure_parent(path)
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write("")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def list_channel_videos(config: YouTubeConfig) -> list[dict[str, Any]]:
    """
    Fetch all videos from a YouTube channel using scrapetube.
    Returns list of {video_id, title, published_at, view_count, duration}.
    """
    videos: list[dict[str, Any]] = []

    # scrapetube expects username without "@", or can take channel_url
    handle = config.channel_handle
    if handle.startswith("@"):
        username = handle[1:]
        kwargs = {"channel_username": username}
    else:
        kwargs = {"channel_url": f"https://www.youtube.com/{handle}"}

    try:
        for video in scrapetube.get_channel(**kwargs):
            # Title can be nested differently depending on video type
            title_obj = video.get("title", {})
            title = (
                title_obj.get("simpleText")
                or (title_obj.get("runs") or [{}])[0].get("text", "")
            )
            videos.append({
                "video_id": video.get("videoId"),
                "title": title,
                "published_at": video.get("publishedTimeText", {}).get("simpleText", ""),
                "view_count": video.get("viewCountText", {}).get("simpleText", ""),
                "duration": video.get("lengthText", {}).get("simpleText", ""),
            })

            if config.max_videos > 0 and len(videos) >= config.max_videos:
                break

    except Exception as exc:
        raise RuntimeError(f"Failed to list videos from channel {config.channel_handle}: {exc}") from exc

    return videos


def _build_api(cookies_file: str | None = None) -> YouTubeTranscriptApi:
    """Build a YouTubeTranscriptApi instance, optionally with cookies for IP ban workaround."""
    if cookies_file:
        cookie_jar = http.cookiejar.MozillaCookieJar(cookies_file)
        cookie_jar.load(ignore_discard=True, ignore_expires=True)
        session = requests.Session()
        session.cookies = cookie_jar  # type: ignore[assignment]
        return YouTubeTranscriptApi(http_client=session)
    return YouTubeTranscriptApi()


def fetch_transcript(video_id: str, language: str = "en", cookies_file: str | None = None) -> str | None:
    """
    Fetch transcript for a single video.
    Returns the full transcript as text, or None if not available.
    Pass cookies_file (Netscape cookies.txt) to bypass YouTube IP blocks.
    """
    try:
        api = _build_api(cookies_file)
        transcript_list = api.fetch(video_id, languages=[language])
        formatter = TextFormatter()
        transcript = formatter.format_transcript(transcript_list)
        return transcript

    except Exception:
        return None


def run_extraction(config: YouTubeConfig, root: Path) -> dict[str, Path]:
    """
    Main extraction pipeline: list videos, fetch transcripts, write outputs.

    Outputs:
    - data/raw/youtube/{slug}_videos.json
    - data/interim/youtube/{slug}_transcripts.csv
    - data/interim/youtube/{slug}_transcripts_full.json (full transcript text)
    - data/interim/youtube/{slug}_summary.json
    """
    print(f"Fetching videos from {config.channel_handle}...")
    videos = list_channel_videos(config)
    print(f"Found {len(videos)} videos")

    print("Fetching transcripts...")
    transcript_rows: list[dict[str, Any]] = []
    transcripts_full: list[dict[str, Any]] = []
    video_data: list[dict[str, Any]] = []
    skipped_count = 0

    for i, video in enumerate(videos):
        print(f"  [{i+1}/{len(videos)}] {video['title'][:60]}...", end=" ", flush=True)

        video_id = video["video_id"]
        transcript_text = fetch_transcript(video_id, config.language, config.cookies_file)

        if transcript_text is None:
            print("⊘ NO TRANSCRIPT")
            skipped_count += 1
            continue

        print(f"✓ ({len(transcript_text)} chars)")

        # Store video metadata with transcript
        video_record = {
            **video,
            "transcript_length": len(transcript_text),
            "transcript_available": True,
        }
        video_data.append(video_record)

        # Create transcript row for CSV
        transcript_rows.append({
            "video_id": video_id,
            "title": video["title"],
            "published_at": video["published_at"],
            "view_count": video["view_count"],
            "duration": video["duration"],
            "transcript_length": len(transcript_text),
        })

        # Store full transcript for later extraction
        transcripts_full.append({
            "video_id": video_id,
            "title": video["title"],
            "published_at": video["published_at"],
            "transcript_text": transcript_text,
        })

    # Write outputs
    slug = slugify(config.output_prefix)

    raw_path = root / "data" / "raw" / "youtube" / f"{slug}_videos.json"
    transcripts_csv = root / "data" / "interim" / "youtube" / f"{slug}_transcripts.csv"
    transcripts_full_json = root / "data" / "interim" / "youtube" / f"{slug}_transcripts_full.json"
    summary_json = root / "data" / "interim" / "youtube" / f"{slug}_summary.json"

    # Write raw videos + metadata (but NOT full transcripts to JSON, too large)
    raw_payload = {
        "channel": config.channel_handle,
        "videos_processed": len(video_data),
        "videos_skipped": skipped_count,
        "videos": video_data,
    }
    write_json(raw_path, raw_payload)

    # Write transcript summary CSV
    write_csv(transcripts_csv, transcript_rows)

    # Write full transcripts as JSON for site extraction
    write_json(transcripts_full_json, {
        "channel": config.channel_handle,
        "transcripts": transcripts_full,
    })

    # Write summary
    summary = {
        "channel": config.channel_handle,
        "videos_with_transcripts": len(video_data),
        "videos_skipped": skipped_count,
        "total_videos_found": len(videos),
        "output_files": {
            "raw_json": str(raw_path),
            "transcripts_csv": str(transcripts_csv),
            "transcripts_full_json": str(transcripts_full_json),
        },
    }
    write_json(summary_json, summary)

    return {
        "raw_json": raw_path,
        "transcripts_csv": transcripts_csv,
        "transcripts_full_json": transcripts_full_json,
        "summary_json": summary_json,
    }
