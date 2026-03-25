#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    print("Checkpoint 1")
    print("Input sources belong in data/raw/")
    print("Normalize extracted rows into the shared WGS84 GeoJSON:")
    print(ROOT / "data" / "output" / "sites_wgs84.geojson")
    print("Required properties: site_name, source_name")


if __name__ == "__main__":
    main()
