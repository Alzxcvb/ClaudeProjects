from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import imageio_ffmpeg
import yt_dlp
from yt_dlp.utils import DownloadError


@dataclass
class VideoInfo:
    video_id: str
    title: str
    duration_seconds: int
    upload_date: str
    url: str
    description: str
    view_count: int | None


def _ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def _normalize_channel_url(channel_url: str) -> str:
    if channel_url.startswith("@"):
        return f"https://www.youtube.com/{channel_url}"
    return channel_url


def _videos_playlist_url(channel_url: str) -> str:
    base = _normalize_channel_url(channel_url).rstrip("/")
    # WHY: appending /videos targets the uploads tab so extract_flat returns a playlist-like list
    if base.endswith("/videos"):
        return base
    return f"{base}/videos"


def _common_opts(cookies_file: str | None) -> dict[str, Any]:
    opts: dict[str, Any] = {"quiet": True, "no_warnings": True, "skip_download": True}
    if cookies_file:
        opts["cookiefile"] = cookies_file
    return opts


def _entry_to_video_info(entry: dict[str, Any]) -> VideoInfo:
    vid = entry.get("id") or ""
    url = entry.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else "")
    duration = entry.get("duration")
    view_count = entry.get("view_count")
    return VideoInfo(
        video_id=vid,
        title=entry.get("title") or "",
        duration_seconds=int(duration) if isinstance(duration, (int, float)) else 0,
        upload_date=entry.get("upload_date") or "",
        url=url if url.startswith("http") else f"https://www.youtube.com/watch?v={vid}",
        description=entry.get("description") or "",
        view_count=int(view_count) if isinstance(view_count, (int, float)) else None,
    )


def list_channel_videos_ytdlp(
    channel_url: str, max_videos: int = 0, cookies_file: str | None = None
) -> list[VideoInfo]:
    playlist_url = _videos_playlist_url(channel_url)
    opts = _common_opts(cookies_file)
    opts["extract_flat"] = "in_playlist"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
    except DownloadError as exc:
        raise RuntimeError(f"Failed to list videos from {channel_url}: {exc}") from exc

    entries = (info or {}).get("entries") or []
    videos: list[VideoInfo] = []
    for entry in entries:
        if not entry:
            continue
        videos.append(_entry_to_video_info(entry))
        if max_videos > 0 and len(videos) >= max_videos:
            break
    return videos


def download_audio_mp3(
    video_id: str, out_dir: Path, cookies_file: str | None = None
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{video_id}.mp3"
    if out_path.exists():
        return out_path

    ffmpeg_path = _ffmpeg_exe()
    opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": str(out_dir / f"{video_id}.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": ffmpeg_path,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
    if cookies_file:
        opts["cookiefile"] = cookies_file

    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except DownloadError as exc:
        raise RuntimeError(f"Failed to download audio for {video_id}: {exc}") from exc

    if not out_path.exists():
        raise RuntimeError(f"Audio file missing after download for {video_id}: {out_path}")
    return out_path


def extract_frame_at_timestamp(
    video_id: str,
    timestamp_seconds: float,
    out_dir: Path,
    cookies_file: str | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ms = int(timestamp_seconds * 1000)
    out_path = out_dir / f"{video_id}_{ms:08d}ms.jpg"
    if out_path.exists():
        return out_path

    opts: dict[str, Any] = {
        "format": "best[height<=720]",
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    if cookies_file:
        opts["cookiefile"] = cookies_file

    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as exc:
        raise RuntimeError(f"Failed to resolve stream URL for {video_id}: {exc}") from exc

    stream_url = (info or {}).get("url")
    if not stream_url:
        raise RuntimeError(f"No direct stream URL returned for {video_id}")

    ffmpeg_path = _ffmpeg_exe()
    # WHY: -ss before -i enables fast seeking without reading the whole stream
    cmd = [
        ffmpeg_path,
        "-y",
        "-ss",
        str(timestamp_seconds),
        "-i",
        stream_url,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not out_path.exists():
        raise RuntimeError(
            f"ffmpeg failed for {video_id} at {timestamp_seconds}s: {result.stderr.strip()[:500]}"
        )
    return out_path
