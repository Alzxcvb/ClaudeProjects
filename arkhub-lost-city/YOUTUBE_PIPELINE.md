# YouTube Transcript Pipeline

Extract historical sites from YouTube channel transcripts.

## Overview

This pipeline processes videos from the "Pillars of the Past" channel (`@PillarsofthePast101`):

1. **youtube_extractor**: Lists all videos from the channel, fetches auto-generated captions
2. **site_extractor**: Extracts historical site mentions using regex patterns, deduplicates across videos
3. **youtube_pipeline.py**: CLI orchestrator

## Usage

```bash
# Fetch all videos and transcripts
python scripts/youtube_pipeline.py --channel "@PillarsofthePast101"

# Limit to 5 videos (for testing)
python scripts/youtube_pipeline.py --channel "@PillarsofthePast101" --max-videos 5

# Use Claude AI for better site extraction (requires ANTHROPIC_API_KEY)
python scripts/youtube_pipeline.py --use-claude
```

## Dependencies

Add to your environment:
```bash
pip install scrapetube youtube-transcript-api
# Optional: anthropic (for --use-claude flag)
```

See `requirements.txt` for the full list.

## Output Files

After running the pipeline, check:

- `data/interim/youtube/pillars-of-past_transcripts.csv` — metadata for each video
- `data/interim/youtube/pillars-of-past_transcripts_full.json` — full transcript text per video
- `data/interim/youtube/pillars-of-past_sites_master.csv` — **deduped sites across all videos**
- `data/interim/youtube/pillars-of-past_sites_per_video.csv` — raw site mentions per video

## Site Extraction Details

### Current Method: Regex-Based (Phase 1)

Patterns:
- `"the ancient city of [X]"`, `"[X] temple complex"`, `"ruins of [X]"`
- Capitalized proper nouns followed by site-type keywords: `temple, city, tomb, palace, settlement, fort, monument, cave, necropolis, harbor, pyramid, ziggurat`

Deduplication:
- Normalized names (lowercase, stripped punctuation, removed common suffixes)
- Aggregates video mentions per unique site
- Outputs: site name, mention count, sample context, video cross-references

### Future Method: Claude AI (Phase 2)

Once an `ANTHROPIC_API_KEY` is configured:
```bash
python scripts/youtube_pipeline.py --use-claude
```

Claude will extract:
- `site_name`: canonical name
- `site_type`: temple, city, tomb, palace, etc.
- `country`, `region`: modern location
- `civilization`: culture (Egyptian, Mayan, Roman, etc.)
- `period`: date range or era
- `discovery_status`: known (already found) / lost (being sought) / uncertain

## Architecture

Follows the arkhub module pattern from `academic_extractor.py`:

```
youtube_extractor.py
  ├─ YouTubeConfig (dataclass with tunable params)
  ├─ list_channel_videos() → video list
  ├─ fetch_transcript() → transcript text
  └─ run_extraction() → outputs raw JSON + CSVs

site_extractor.py
  ├─ ExtractionConfig
  ├─ extract_candidate_sites() → regex-based extraction
  ├─ stub_claude_extraction() → placeholder for AI
  └─ run_extraction() → outputs deduped sites + summaries

youtube_pipeline.py (CLI)
  └─ orchestrates 1→2, prints summary
```

## Troubleshooting

**Issue: "No module named 'scrapetube'"**
- Install: `pip install scrapetube youtube-transcript-api`
- If using a venv, activate it first

**Issue: Videos skip with "⊘ NO TRANSCRIPT"**
- Channel videos without auto-captions or manually uploaded transcripts will be skipped
- YouTube auto-generates captions for most videos, but some may fail if audio is too unclear

**Issue: Site extraction returns no results**
- The regex patterns are conservative to avoid false positives
- Try manual review of `pillars-of-past_sites_per_video.csv` to see what was extracted
- For better results, use `--use-claude` once configured

## Next Steps

1. Install dependencies: `pip install -r requirements.txt`
2. Run smoke test: `python scripts/youtube_pipeline.py --max-videos 5`
3. Review outputs in `data/interim/youtube/`
4. (Optional) Add `ANTHROPIC_API_KEY` and rerun with `--use-claude` for richer extraction
