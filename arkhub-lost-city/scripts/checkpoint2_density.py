#!/usr/bin/env python3
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITES = ROOT / "data" / "output" / "sites_wgs84.geojson"
CANDIDATES = ROOT / "data" / "output" / "candidate_tiles.geojson"


def main() -> None:
    with SITES.open() as f:
        sites = json.load(f).get("features", [])

    print("Checkpoint 2")
    print(f"Loaded {len(sites)} known site point(s)")
    print("Next implementation step: convert points into density-ranked candidate tiles")
    print(f"Write ranked bounding boxes to {CANDIDATES}")


if __name__ == "__main__":
    main()
