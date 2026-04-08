#!/usr/bin/env python
"""
YouTube transcript pipeline for Pillars of the Past channel.

Usage:
    python scripts/youtube_pipeline.py --channel "@PillarsofthePast101" [--max-videos 10]
"""

import argparse
import csv
import sys
from pathlib import Path

# Add src to path so we can import arkhub modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arkhub.youtube_extractor import YouTubeConfig, run_extraction as run_youtube_extraction
from arkhub.site_extractor import ExtractionConfig, run_extraction as run_site_extraction


def load_transcripts_from_json(json_path: Path) -> list[dict[str, str]]:
    """Load full transcripts from the JSON file created by youtube_extractor."""
    import json

    if not json_path.exists():
        return []

    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("transcripts", [])


def main():
    parser = argparse.ArgumentParser(
        description="Extract historical sites from YouTube Pillars of the Past transcripts"
    )
    parser.add_argument(
        "--channel",
        default="@PillarsofthePast101",
        help="YouTube channel handle (default: @PillarsofthePast101)",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=0,
        help="Max videos to fetch (0 = all, default: 0)",
    )
    parser.add_argument(
        "--use-claude",
        action="store_true",
        help="Use Claude API for site extraction (requires ANTHROPIC_API_KEY)",
    )
    parser.add_argument(
        "--model",
        default="claude-haiku-4-5-20251001",
        help="Claude model to use for extraction",
    )

    args = parser.parse_args()

    # Determine project root
    root = Path(__file__).resolve().parent.parent

    print("=" * 60)
    print("YouTube Transcript Site Extractor")
    print("=" * 60)
    print(f"Channel:       {args.channel}")
    print(f"Max videos:    {args.max_videos if args.max_videos > 0 else 'all'}")
    print(f"Use Claude:    {args.use_claude}")
    print()

    # Step 1: Fetch videos and transcripts
    print("STEP 1: Fetching videos and transcripts from YouTube channel...")
    print("-" * 60)

    youtube_config = YouTubeConfig(
        channel_handle=args.channel,
        max_videos=args.max_videos,
        output_prefix="pillars-of-past",
    )

    youtube_outputs = run_youtube_extraction(youtube_config, root)
    print()
    print(f"✓ Transcripts saved to: {youtube_outputs['transcripts_csv']}")
    print()

    # Step 2: Extract sites from transcripts
    print("STEP 2: Extracting historical sites from transcripts...")
    print("-" * 60)

    # Load full transcripts from JSON
    transcripts = load_transcripts_from_json(youtube_outputs["transcripts_full_json"])
    print(f"Loaded {len(transcripts)} transcripts")

    if len(transcripts) == 0:
        print("No transcripts found to extract sites from.")
    else:
        site_config = ExtractionConfig(
            output_prefix="pillars-of-past",
            use_claude=args.use_claude,
            model=args.model,
        )

        site_outputs = run_site_extraction(site_config, transcripts, root)
        print()
        print(f"✓ Sites saved to: {site_outputs['sites_master_csv']}")
        print()

    # Step 3: Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Videos processed:  {len(transcripts)}")
    print(f"Transcripts saved: {youtube_outputs['transcripts_csv']}")
    print()
    print("Next steps:")
    print("1. Check data/interim/youtube/ for CSV outputs")
    print("2. Verify site extraction results")
    print("3. To use Claude for better extraction, set ANTHROPIC_API_KEY and use --use-claude")
    print()


if __name__ == "__main__":
    main()
