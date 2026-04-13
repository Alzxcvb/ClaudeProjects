# YouTube Transcript Pipeline

Extract historical sites from YouTube channel transcripts. Two pipelines are available:

| Pipeline | Stack | Timestamps | Frames | Speed |
|---|---|---|---|---|
| **Simple** | `scrapetube` + `youtube-transcript-api` | none | no | fast |
| **Best** | `yt-dlp` + AssemblyAI + `ffmpeg` | word-level | yes | slow, richer output |

Both target the "Pillars of the Past" channel (`@PillarsofthePast101`) by default.

## Simple Pipeline

1. `src/arkhub/youtube_extractor.py` — scrapetube lists videos, youtube-transcript-api fetches auto-captions
2. `src/arkhub/site_extractor.py` — regex patterns extract site mentions, dedupes across videos
3. `scripts/youtube_pipeline.py` — CLI orchestrator

```bash
python scripts/youtube_pipeline.py --channel "@PillarsofthePast101"
python scripts/youtube_pipeline.py --max-videos 5                 # smoke test
python scripts/youtube_pipeline.py --use-claude                   # ANTHROPIC_API_KEY required
```

Trade-off: fast but misses a lot — auto-captions drop punctuation/casing, no word-level timestamps, and no way to screenshot the video at a specific mention.

## Best Pipeline

1. `src/arkhub/youtube_audio.py` — yt-dlp lists videos, downloads `bestaudio` → MP3, and resolves direct stream URLs for frame capture
2. `src/arkhub/assemblyai_transcriber.py` — AssemblyAI `best` speech model returns word-level timestamps
3. `src/arkhub/site_extractor.py::extract_sites_from_words` — maps regex matches over the joined text back to the word index, so each site mention carries `start_seconds` / `end_seconds`
4. `src/arkhub/youtube_audio.py::extract_frame_at_timestamp` — ffmpeg fast-seek (`-ss` before `-i`) against the direct stream URL, writes one JPG per site mention
5. `scripts/youtube_pipeline_best.py` — CLI orchestrator

```bash
export ASSEMBLYAI_API_KEY=...
python scripts/youtube_pipeline_best.py --max-videos 1            # full pipeline (listing → audio → transcription → sites → frames)
python scripts/youtube_pipeline_best.py --no-transcribe           # audio-only (no key needed)
python scripts/youtube_pipeline_best.py --skip-frames              # transcript + sites without frame capture
python scripts/youtube_pipeline_best.py --max-frames-per-video 5  # cap frame downloads per video (default: 10)
```

Artifacts are cached: re-running with the same `--max-videos` will skip already-downloaded MP3s, existing transcripts under `transcripts_word/`, and existing frames.

## Dependencies

```bash
pip install -r requirements.txt
```

`imageio-ffmpeg` provides a bundled static `ffmpeg` binary, so you don't need a system install. The best pipeline reads the path via `imageio_ffmpeg.get_ffmpeg_exe()`.

## Output Files

**Simple pipeline** (`youtube_pipeline.py`):

- `data/interim/youtube/pillars-of-past_transcripts.csv` — metadata for each video
- `data/interim/youtube/pillars-of-past_transcripts_full.json` — full transcript text per video
- `data/interim/youtube/pillars-of-past_sites_master.csv` — **deduped sites across all videos**
- `data/interim/youtube/pillars-of-past_sites_per_video.csv` — raw site mentions per video

**Best pipeline** (`youtube_pipeline_best.py`):

- `data/raw/youtube/audio/{video_id}.mp3` — downloaded audio per video
- `data/raw/youtube/frames/{video_id}_{ms:08d}ms.jpg` — JPG frame at each site-mention timestamp
- `data/raw/youtube/pillars-of-past-best_videos_ytdlp.json` — yt-dlp video listing
- `data/interim/youtube/transcripts_word/{video_id}.json` — AssemblyAI word-level transcripts
- `data/interim/youtube/pillars-of-past-best_sites_timed.csv` — every site mention w/ timestamps + `youtu.be/{id}?t={s}` URL
- `data/interim/youtube/pillars-of-past-best_sites_master.csv` — deduped sites across videos
- `data/interim/youtube/pillars-of-past-best_summary.json` — run totals

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
