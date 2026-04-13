#!/usr/bin/env python
"""
"Best way" YouTube pipeline for Pillars of the Past.

Stack:
  1. yt-dlp              -> list channel videos + download MP3 audio
  2. AssemblyAI          -> transcribe MP3 with word-level timestamps
  3. site_extractor      -> extract archaeological site mentions w/ timestamps
  4. yt-dlp + ffmpeg     -> grab a video frame at each site-mention timestamp

Usage:
    python scripts/youtube_pipeline_best.py --channel "@PillarsofthePast101" --max-videos 3
    python scripts/youtube_pipeline_best.py --max-videos 1 --skip-frames    # faster smoke test
    python scripts/youtube_pipeline_best.py --no-transcribe                 # audio + listing only

Requires:
    ASSEMBLYAI_API_KEY env var (unless --no-transcribe)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arkhub.youtube_audio import (
    VideoInfo,
    download_audio_mp3,
    extract_frame_at_timestamp,
    list_channel_videos_ytdlp,
)
from arkhub.assemblyai_transcriber import (
    TranscriptResult,
    batch_transcribe,
    load_transcript,
    save_transcript,
    transcribe_audio,
)
from arkhub.site_extractor import (
    TimedSiteMention,
    extract_sites_from_words,
)


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


def _videos_to_rows(videos: list[VideoInfo]) -> list[dict]:
    return [asdict(v) for v in videos]


def _words_to_dicts(result: TranscriptResult) -> list[dict]:
    return [
        {
            "text": w.text,
            "start_seconds": w.start_seconds,
            "end_seconds": w.end_seconds,
            "confidence": w.confidence,
        }
        for w in result.words
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--channel", default="@PillarsofthePast101")
    parser.add_argument("--max-videos", type=int, default=0, help="0 = all")
    parser.add_argument("--output-prefix", default="pillars-of-past-best")
    parser.add_argument("--cookies", default=None, help="Netscape cookies.txt (optional)")
    parser.add_argument("--no-transcribe", action="store_true",
                        help="Skip AssemblyAI (download audio only)")
    parser.add_argument("--skip-frames", action="store_true",
                        help="Skip frame extraction at site timestamps")
    parser.add_argument("--max-frames-per-video", type=int, default=10,
                        help="Cap frames extracted per video (default: 10)")

    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    slug = args.output_prefix.strip().lower().replace(" ", "-") or "pillars-of-past-best"

    audio_dir = root / "data" / "raw" / "youtube" / "audio"
    frame_dir = root / "data" / "raw" / "youtube" / "frames"
    transcript_dir = root / "data" / "interim" / "youtube" / "transcripts_word"
    interim_dir = root / "data" / "interim" / "youtube"
    videos_json = root / "data" / "raw" / "youtube" / f"{slug}_videos_ytdlp.json"
    sites_master_csv = interim_dir / f"{slug}_sites_master.csv"
    sites_timed_csv = interim_dir / f"{slug}_sites_timed.csv"
    summary_json = interim_dir / f"{slug}_summary.json"

    print("=" * 70)
    print("YouTube Pipeline (Best Way): yt-dlp + AssemblyAI + frame capture")
    print("=" * 70)
    print(f"Channel:              {args.channel}")
    print(f"Max videos:           {args.max_videos or 'all'}")
    print(f"Transcribe:           {'yes' if not args.no_transcribe else 'no'}")
    print(f"Extract frames:       {'yes' if not args.skip_frames else 'no'}")
    print(f"Audio dir:            {audio_dir}")
    print(f"Transcripts dir:      {transcript_dir}")
    print(f"Frames dir:           {frame_dir}")
    print()

    print("STEP 1/4: Listing videos from channel via yt-dlp...")
    print("-" * 70)
    videos = list_channel_videos_ytdlp(
        args.channel, max_videos=args.max_videos, cookies_file=args.cookies
    )
    print(f"Found {len(videos)} videos")
    for v in videos[:10]:
        print(f"  {v.video_id}  {v.title[:70]}")
    _write_json(videos_json, {
        "channel": args.channel,
        "count": len(videos),
        "videos": _videos_to_rows(videos),
    })
    print(f"Wrote: {videos_json}")
    print()

    if not videos:
        print("No videos found. Exiting.")
        return

    print("STEP 2/4: Downloading audio (MP3) for each video...")
    print("-" * 70)
    mp3_jobs: list[tuple[str, Path]] = []
    for i, v in enumerate(videos, start=1):
        print(f"  [{i}/{len(videos)}] {v.video_id}  {v.title[:60]}")
        try:
            mp3 = download_audio_mp3(v.video_id, audio_dir, cookies_file=args.cookies)
            size_mb = mp3.stat().st_size / (1024 * 1024) if mp3.exists() else 0.0
            print(f"          -> {mp3.name}  ({size_mb:.1f} MB)")
            mp3_jobs.append((v.video_id, mp3))
        except Exception as exc:
            print(f"          ! download failed: {exc}")
    print(f"Audio downloaded: {len(mp3_jobs)}/{len(videos)}")
    print()

    if args.no_transcribe:
        print("(Skipping transcription per --no-transcribe.)")
        return

    if not os.environ.get("ASSEMBLYAI_API_KEY"):
        print("! ASSEMBLYAI_API_KEY not set. Transcription will fail.")
        print("  Export the key and re-run; audio files are cached so step 2 will be skipped.")
        return

    print("STEP 3/4: Transcribing audio via AssemblyAI (word-level timestamps)...")
    print("-" * 70)
    transcripts = batch_transcribe(mp3_jobs, transcript_dir, skip_existing=True)
    print(f"Transcripts: {len(transcripts)}/{len(mp3_jobs)}")
    print()

    videos_by_id = {v.video_id: v for v in videos}

    print("STEP 4/4: Extracting site mentions + frames at timestamps...")
    print("-" * 70)
    all_mentions: list[TimedSiteMention] = []
    frames_written = 0
    for t in transcripts:
        title = videos_by_id.get(t.video_id, VideoInfo("", "", 0, "", "", "", None)).title
        word_dicts = _words_to_dicts(t)
        mentions = extract_sites_from_words(word_dicts, t.video_id, title)
        print(f"  {t.video_id}: {len(mentions)} site mentions")
        all_mentions.extend(mentions)

        if args.skip_frames:
            continue

        for m in mentions[: args.max_frames_per_video]:
            try:
                frame_path = extract_frame_at_timestamp(
                    m.video_id, m.start_seconds, frame_dir, cookies_file=args.cookies
                )
                frames_written += 1
                print(f"    frame: {m.site_name} @ {m.start_seconds:.1f}s -> {frame_path.name}")
            except Exception as exc:
                print(f"    ! frame failed for {m.site_name} @ {m.start_seconds:.1f}s: {exc}")
    print(f"Frames extracted: {frames_written}")
    print()

    timed_rows: list[dict] = []
    master: dict[str, dict] = {}
    for m in all_mentions:
        timed_rows.append({
            "site_name": m.site_name,
            "normalized_name": m.normalized_name,
            "video_id": m.video_id,
            "video_title": m.video_title,
            "start_seconds": round(m.start_seconds, 2),
            "end_seconds": round(m.end_seconds, 2),
            "youtube_url_ts": f"https://youtu.be/{m.video_id}?t={int(m.start_seconds)}",
            "context_snippet": m.context_snippet,
        })
        bucket = master.setdefault(m.normalized_name, {
            "site_name": m.site_name,
            "normalized_name": m.normalized_name,
            "mention_count": 0,
            "video_count": 0,
            "video_ids": set(),
            "first_url_ts": f"https://youtu.be/{m.video_id}?t={int(m.start_seconds)}",
            "sample_context": m.context_snippet[:200],
        })
        bucket["mention_count"] += 1
        bucket["video_ids"].add(m.video_id)

    master_rows: list[dict] = []
    for b in sorted(master.values(), key=lambda x: -x["mention_count"]):
        b["video_count"] = len(b["video_ids"])
        b["video_ids"] = "; ".join(sorted(b["video_ids"]))
        master_rows.append(b)

    _write_csv(sites_timed_csv, timed_rows)
    _write_csv(sites_master_csv, master_rows)

    _write_json(summary_json, {
        "channel": args.channel,
        "videos_listed": len(videos),
        "audio_downloaded": len(mp3_jobs),
        "transcripts": len(transcripts),
        "total_mentions": len(all_mentions),
        "unique_sites": len(master_rows),
        "frames_extracted": frames_written,
        "outputs": {
            "videos_json": str(videos_json),
            "sites_timed_csv": str(sites_timed_csv),
            "sites_master_csv": str(sites_master_csv),
            "transcripts_dir": str(transcript_dir),
            "audio_dir": str(audio_dir),
            "frames_dir": str(frame_dir),
        },
    })

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Videos listed:     {len(videos)}")
    print(f"Audio downloaded:  {len(mp3_jobs)}")
    print(f"Transcripts:       {len(transcripts)}")
    print(f"Site mentions:     {len(all_mentions)}")
    print(f"Unique sites:      {len(master_rows)}")
    print(f"Frames extracted:  {frames_written}")
    print()
    print(f"Master CSV: {sites_master_csv}")
    print(f"Timed CSV:  {sites_timed_csv}")
    print(f"Summary:    {summary_json}")


if __name__ == "__main__":
    main()
