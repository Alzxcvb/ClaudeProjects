# Academic Extractor

Reusable metadata search tool for archaeology or any other research study.

Purpose:

- search OpenAlex and Crossref
- normalize paper metadata
- reconstruct OpenAlex abstracts when available
- extract explicit coordinate mentions from titles and abstracts
- export reviewable CSV and JSON outputs

## Why this is useful

For the hackathon, this gives you a fast first-pass list of archaeology papers that may contain site coordinates or directly mention known sites. For future studies, change only the query string and output prefix.

## CLI

```bash
cd /Users/alexandercoffman/ClaudeProjects/arkhub-lost-city
PYTHONPATH=src python3 scripts/academic_paper_extractor.py \
  --query "Peru archaeology desert geoglyph site coordinates" \
  --provider openalex \
  --provider crossref \
  --per-page 20 \
  --pages 2 \
  --output-prefix peru_desert_archaeology
```

Optional flags:

- `--mailto you@example.com`
- `--min-year 2000`

## Outputs

- `data/raw/academic/<prefix>_works.json`
- `data/interim/academic/<prefix>_papers.csv`
- `data/interim/academic/<prefix>_coordinate_mentions.csv`
- `data/interim/academic/<prefix>_summary.json`

## Recommended workflow for Step 1

1. Run a broad query:
   `Peru archaeology desert site coordinates`
2. Run narrower follow-ups:
   `Nazca geoglyph coordinates archaeology`
   `Peruvian desert archaeological survey coordinates`
   `Andean coast archaeology remote sensing coordinates`
3. Review `*_coordinate_mentions.csv` first.
4. Review `*_papers.csv` for papers with relevant site names even if no coordinate pair was extracted.
5. Manually promote confirmed sites into the shared GeoJSON.

## Limitations

- This searches metadata, titles, and abstracts. It does not parse full PDFs by itself.
- Many papers keep coordinates in tables, figures, supplements, or full text.
- Coordinate extraction is regex-based and should be reviewed manually.
- Crossref abstract coverage is inconsistent.

## Extension points

- add Semantic Scholar or Europe PMC as another provider
- add PDF text extraction for locally saved papers
- add named-site extraction from titles and abstracts
- map extracted coordinates directly into GeoJSON features after review
