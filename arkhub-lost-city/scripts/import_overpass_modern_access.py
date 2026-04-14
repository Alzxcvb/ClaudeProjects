#!/usr/bin/env python3
"""
Convert Overpass JSON exports into local GeoJSON layers for filter_modern_access.py.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
TMP = ROOT / "data/raw/modern_access/tmp"
OUT = ROOT / "data/raw/modern_access"

TMP.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)


def feature(name, geometry, props):
    return {
        "type": "Feature",
        "properties": {"name": name, **props},
        "geometry": geometry,
    }


def load_elements(path):
    data = json.loads(path.read_text())
    return data.get("elements", [])


def write_geojson(path, features):
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, indent=2))
    print(f"Wrote {len(features)} features -> {path}")


def import_points(src_name, out_name, point_label):
    src = TMP / src_name
    if not src.exists():
        print(f"Missing {src}")
        return
    features = []
    for el in load_elements(src):
        if el.get("type") != "node":
            continue
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            continue
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("operator") or point_label
        features.append(
            feature(
                name,
                {"type": "Point", "coordinates": [lon, lat]},
                tags,
            )
        )
    write_geojson(OUT / out_name, features)


def import_lines(src_name, out_name, fallback_name):
    src = TMP / src_name
    if not src.exists():
        print(f"Missing {src}")
        return
    features = []
    for el in load_elements(src):
        if el.get("type") not in {"way", "relation"}:
            continue
        geom = el.get("geometry") or []
        if len(geom) < 2:
            continue
        coords = [[pt["lon"], pt["lat"]] for pt in geom]
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("ref") or fallback_name
        features.append(
            feature(
                name,
                {"type": "LineString", "coordinates": coords},
                tags,
            )
        )
    write_geojson(OUT / out_name, features)


def main():
    import_lines("roads.json", "major_roads.geojson", "major_road")
    import_points("postal.json", "postal_points.geojson", "postal_service")
    import_points("airports.json", "airports.geojson", "airport")
    import_points("ports.json", "ports.geojson", "port")


if __name__ == "__main__":
    main()
