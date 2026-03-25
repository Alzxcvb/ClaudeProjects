# Simplified Checkpoints

## Checkpoint 1: Collect Known Sites

Timebox: 45 minutes

Goal: build one trusted map of known archaeological sites in Peru's desert regions.

Steps:

1. Split source hunting into parallel tracks.
2. Normalize every find to `name + lat + lon + source`.
3. Resolve place names to coordinates only when the source is strong enough.
4. Deduplicate by distance, name similarity, and source overlap.
5. Export everything to the shared WGS84 GeoJSON.

Track assignments:

- Track A: YouTube review
  - Extract site names, coordinates, discovery strategies, and visual signatures from "Pillars of the Past".
- Track B: OpenAI A-Z challenge resources
  - Pull Peruvian archaeology references and convert them into site rows.
- Track C: Web + academic search
  - Focus on papers, Wikipedia lists, Google Scholar, ScienceDirect.
- Track D: Community maps
  - Review iNaturalist, Google Earth pins, and community-maintained desert markers.

Definition of done:

- `data/output/sites_wgs84.geojson` exists.
- Every feature has coordinates and provenance.
- Low-confidence rows are labeled, not deleted.

Deliverable:

- Master site map
- Source count by track
- Rough count of unique sites

## Checkpoint 2: Score Dense Areas

Timebox: 45 minutes

Goal: turn known site points into ranked search areas.

Steps:

1. Load the master GeoJSON.
2. Run KDE or a simpler fallback:
   density by grid cell + nearest-neighbor distance.
3. Identify dense clusters and nearby spatial gaps.
4. Add heuristic boosts for likely archaeology-friendly terrain:
   paleo-channels, plateaus, route corridors, edges of known complexes.
5. Convert top-ranked areas into bounding boxes.

Fallback if time is tight:

- Use a regular lat/lon grid over the study area.
- Count sites per cell.
- Add score for cells near dense cells but with fewer known sites.

Definition of done:

- Ranked tile list with lat/lon bounds
- `data/output/candidate_tiles.geojson`
- CSV or JSON summary of top candidates

Deliverable:

- Top 10 to 30 candidate tiles ranked by score

## Checkpoint 3: Pull Imagery

Timebox: 45 minutes

Goal: collect satellite imagery for the top candidate tiles.

Steps:

1. Take the top candidate bounding boxes.
2. Choose one imagery source first:
   Sentinel Hub or Google Earth Engine.
3. Filter for dry season and cloud cover under 10 percent where possible.
4. Export one analysis-friendly GeoTIFF and one vision-friendly PNG or JPEG per tile.
5. Save outputs in folders named by bounding box ID.

Definition of done:

- Imagery saved locally for the top-ranked tiles
- Each tile has metadata:
  source, date, cloud cover, bands, bounding box

Deliverable:

- `data/imagery/<tile_id>/image.tif`
- `data/imagery/<tile_id>/preview.png`
- `data/imagery/index.json`

## Checkpoint 4: Analyze Tiles

Timebox: 45 minutes

Goal: score anomalies with two parallel methods.

### Stream A: Vision

Steps:

1. Feed tile previews to a multimodal model.
2. Ask for geometric anomalies, linear traces, mounds, enclosures, terracing, and unnatural surface patterns.
3. Return structured outputs:
   tile ID, anomaly type, rationale, confidence, approximate location in tile.

### Stream B: Spectral

Steps:

1. Load Sentinel-2 GeoTIFFs.
2. Compute a small set of indices first.
3. Flag sharp local anomalies and structured edges.
4. Compare flagged areas against known sites to avoid rediscovering the input set.

Suggested starting indices:

- NDVI
- BSI
- NDBI where relevant
- Band-ratio experiments inspired by archaeology remote-sensing literature

Definition of done:

- `data/output/vision_flags.json`
- `data/output/spectral_flags.json`
- Ranked tile-level anomaly scores

Deliverable:

- Shortlist of tiles with interpretable reasons

## Checkpoint 5: Merge + Present

Timebox: 30 minutes

Goal: produce a defendable shortlist and a clean one-slide story.

Steps:

1. Merge vision and spectral outputs by tile.
2. Boost tiles flagged by both streams.
3. Overlay results on the master map.
4. Pick the top 3 to 5 candidates.
5. Build one slide with method, evidence, and next steps.

Slide outline:

1. Problem
2. Data sources and site count
3. Pipeline diagram
4. Top candidates with images and reasoning
5. Next steps:
   field verification, higher-resolution imagery, LiDAR, local expert review

Definition of done:

- One submission packet
- One slide
- One ranked candidate list

## Team Mode

If you have 2 to 4 people:

- Person 1: collection lead and GeoJSON QA
- Person 2: density + geospatial scoring
- Person 3: imagery pulling and metadata tracking
- Person 4: analysis + final slide assembly

If solo:

- Prioritize Wikipedia + papers first
- Use grid scoring instead of full KDE if needed
- Analyze only the top 5 to 10 tiles
