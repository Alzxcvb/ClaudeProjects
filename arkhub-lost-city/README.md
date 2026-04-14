# Arkhub: Lost City of the Inkas

Fast-start repo for the NS Archaeology Hackathon.

Goal: ingest known archaeological data for Peru's desert regions, rank promising gaps near known site clusters, pull satellite imagery, and flag anomalies that may indicate undocumented sites.

## Repo Layout

- `data/raw/`: source exports, scraped files, notes, PDFs
- `data/interim/`: normalized intermediate tables
- `data/processed/`: cleaned outputs ready for analysis
- `data/output/`: shared GeoJSON, ranked candidate tiles, final overlays
- `data/imagery/`: satellite tiles grouped by bounding box
- `docs/`: checkpoint playbook and submission notes
- `prompts/`: multimodal analysis prompts
- `scripts/`: per-checkpoint entrypoints
- `src/arkhub/`: shared config and helpers

## Shared Contract

All tracks write archaeological site points to:

- `data/output/sites_wgs84.geojson`

Requirements:

- CRS: WGS84 (`EPSG:4326`)
- Geometry: `Point`
- One feature per known site
- Keep provenance in `properties`

Suggested properties:

- `site_name`
- `source_type`
- `source_name`
- `country`
- `region`
- `confidence`
- `notes`
- `discovery_strategy`
- `visual_signatures`

## Hackathon Run Order

1. Check [docs/checkpoints.md](/Users/alexandercoffman/ClaudeProjects/arkhub-lost-city/docs/checkpoints.md).
2. Fill `data/output/sites_wgs84.geojson` from all collection tracks.
3. Run density scoring to produce ranked candidate tiles.
4. Pull imagery for the top tiles.
5. Run vision + spectral analysis in parallel.
6. Merge results for the final slide and submission.
7. Use [docs/academic-extractor.md](/Users/alexandercoffman/ClaudeProjects/arkhub-lost-city/docs/academic-extractor.md) for paper mining in Checkpoint 1.

## Quick Start

```bash
cd /Users/alexandercoffman/ClaudeProjects/arkhub-lost-city
python3 scripts/validate_geojson.py
python3 scripts/checkpoint2_density.py
python3 scripts/filter_modern_access.py
python3 scripts/checkpoint3_imagery.py
python3 scripts/checkpoint4_analysis.py
PYTHONPATH=src python3 scripts/academic_paper_extractor.py --query "Peru archaeology desert site coordinates"
```

These scripts are safe starter stubs. They define I/O and expected outputs so the team can work in parallel without breaking the pipeline.
