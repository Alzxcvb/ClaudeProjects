#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP_DIR="$ROOT/data/raw/modern_access/tmp"

mkdir -p "$TMP_DIR"

echo "Fetching postal/courier points..."
curl -fsSL 'https://overpass-api.de/api/interpreter' \
  --data-urlencode 'data=[out:json][timeout:120];area["ISO3166-1"="PE"][admin_level=2]->.a;(node["amenity"="post_office"](area.a);node["office"="courier"](area.a);node["shop"="courier"](area.a););out body;' \
  -o "$TMP_DIR/postal.json"

echo "Fetching airports..."
curl -fsSL 'https://overpass-api.de/api/interpreter' \
  --data-urlencode 'data=[out:json][timeout:120];area["ISO3166-1"="PE"][admin_level=2]->.a;(node["aeroway"="aerodrome"](area.a);node["aeroway"="airport"](area.a););out body;' \
  -o "$TMP_DIR/airports.json"

echo "Fetching ports..."
curl -fsSL 'https://overpass-api.de/api/interpreter' \
  --data-urlencode 'data=[out:json][timeout:120];area["ISO3166-1"="PE"][admin_level=2]->.a;(node["harbour"](area.a);node["amenity"="ferry_terminal"](area.a);node["industrial"="port"](area.a);node["landuse"="port"](area.a););out body;' \
  -o "$TMP_DIR/ports.json"

echo "Fetching major roads by study region..."
curl -fsSL 'https://overpass-api.de/api/interpreter' \
  --data-urlencode 'data=[out:json][timeout:120];(way["highway"~"motorway|trunk|primary|secondary"](-9.20,-80.80,-5.80,-77.00);relation["highway"~"motorway|trunk|primary|secondary"](-9.20,-80.80,-5.80,-77.00););out geom;' \
  -o "$TMP_DIR/roads_north.json"
curl -fsSL 'https://overpass-api.de/api/interpreter' \
  --data-urlencode 'data=[out:json][timeout:120];(way["highway"~"motorway|trunk|primary|secondary"](-13.20,-78.00,-10.50,-75.50);relation["highway"~"motorway|trunk|primary|secondary"](-13.20,-78.00,-10.50,-75.50););out geom;' \
  -o "$TMP_DIR/roads_central.json"
curl -fsSL 'https://overpass-api.de/api/interpreter' \
  --data-urlencode 'data=[out:json][timeout:120];(way["highway"~"motorway|trunk|primary|secondary"](-15.50,-76.80,-14.10,-73.80);relation["highway"~"motorway|trunk|primary|secondary"](-15.50,-76.80,-14.10,-73.80););out geom;' \
  -o "$TMP_DIR/roads_south_a.json"
curl -fsSL 'https://overpass-api.de/api/interpreter' \
  --data-urlencode 'data=[out:json][timeout:120];(way["highway"~"motorway|trunk|primary|secondary"](-14.10,-76.80,-12.80,-73.80);relation["highway"~"motorway|trunk|primary|secondary"](-14.10,-76.80,-12.80,-73.80););out geom;' \
  -o "$TMP_DIR/roads_south_b.json"
curl -fsSL 'https://overpass-api.de/api/interpreter' \
  --data-urlencode 'data=[out:json][timeout:120];(way["highway"~"motorway|trunk|primary|secondary"](-15.20,-73.00,-12.50,-70.00);relation["highway"~"motorway|trunk|primary|secondary"](-15.20,-73.00,-12.50,-70.00););out geom;' \
  -o "$TMP_DIR/roads_highlands.json"
curl -fsSL 'https://overpass-api.de/api/interpreter' \
  --data-urlencode 'data=[out:json][timeout:120];(way["highway"~"motorway|trunk|primary|secondary"](-17.80,-72.50,-15.20,-69.80);relation["highway"~"motorway|trunk|primary|secondary"](-17.80,-72.50,-15.20,-69.80););out geom;' \
  -o "$TMP_DIR/roads_far_south.json"

echo "Merging road slices..."
python3 - <<'PY'
import json
from pathlib import Path
base = Path("data/raw/modern_access/tmp")
inputs = [
    "roads_north.json",
    "roads_central.json",
    "roads_south_a.json",
    "roads_south_b.json",
    "roads_highlands.json",
    "roads_far_south.json",
]
seen = set()
elements = []
for name in inputs:
    path = base / name
    data = json.loads(path.read_text())
    for el in data.get("elements", []):
        key = (el.get("type"), el.get("id"))
        if key in seen:
            continue
        seen.add(key)
        elements.append(el)
(base / "roads.json").write_text(json.dumps({"version": 0.6, "generator": "merged", "elements": elements}))
print(f"merged {len(elements)} road elements")
PY

echo "Converting Overpass JSON to GeoJSON..."
python3 "$ROOT/scripts/import_overpass_modern_access.py"

echo "Done. Run: python3 scripts/filter_modern_access.py"
