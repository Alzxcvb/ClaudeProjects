#!/usr/bin/env python3
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITES = ROOT / "data" / "output" / "sites_wgs84.geojson"


def main() -> None:
    if not SITES.exists():
        raise SystemExit(f"Missing file: {SITES}")

    with SITES.open() as f:
        payload = json.load(f)

    if payload.get("type") != "FeatureCollection":
        raise SystemExit("GeoJSON must be a FeatureCollection")

    features = payload.get("features", [])
    for index, feature in enumerate(features):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        if geometry.get("type") != "Point":
            raise SystemExit(f"Feature {index} must be a Point")
        coords = geometry.get("coordinates", [])
        if len(coords) != 2:
            raise SystemExit(f"Feature {index} must have [lon, lat]")
        if "site_name" not in props:
            raise SystemExit(f"Feature {index} missing properties.site_name")
        if "source_name" not in props:
            raise SystemExit(f"Feature {index} missing properties.source_name")

    print(f"Validated {len(features)} feature(s) in {SITES}")


if __name__ == "__main__":
    main()
