#!/usr/bin/env python3
"""Export candidate tiles as AOI GeoJSON in team format.

Output per feature:
  { "type": "Feature",
    "properties": { "aoi_name": "Survey Area 1", "mgrs_zone": "18LYL" },
    "geometry": { "type": "Polygon", "coordinates": [[[lng1,lat1],...]] }
  }
"""
import json, re, mgrs as mgrs_lib
from pathlib import Path

ROOT       = Path(__file__).parent.parent
IN_GEOJSON = ROOT / "data/output/candidate_tiles_v2.geojson"
OUT_GEOJSON= ROOT / "data/output/aoi_survey_areas.geojson"

m = mgrs_lib.MGRS()

def mgrs_zone(lat, lon):
    """Return GZD + 100km square only, e.g. '18LYL'."""
    raw = m.toMGRS(lat, lon, MGRSPrecision=2)   # e.g. '18LYL6644'
    match = re.match(r'^(\d{1,2}[A-Z][A-Z]{2})', raw)
    return match.group(1) if match else raw[:5]

data     = json.loads(IN_GEOJSON.read_text())
features = []

for f in sorted(data["features"], key=lambda x: x["properties"]["global_rank"]):
    p    = f["properties"]
    rank = p["global_rank"]
    lat  = p["lat_center"]
    lon  = p["lon_center"]

    features.append({
        "type": "Feature",
        "properties": {
            "aoi_name":  "Survey Area " + str(rank),
            "mgrs_zone": mgrs_zone(lat, lon),
        },
        "geometry": f["geometry"]
    })

out = {"type": "FeatureCollection", "features": features}
OUT_GEOJSON.write_text(json.dumps(out, indent=2))

print("Written " + str(len(features)) + " AOIs -> " + str(OUT_GEOJSON))
print()
print("Sample (first 5):")
for feat in features[:5]:
    p = feat["properties"]
    coords = feat["geometry"]["coordinates"][0]
    print("  " + p["aoi_name"] + "  mgrs_zone=" + p["mgrs_zone"] +
          "  bbox=" + str(round(coords[0][0],4)) + "," + str(round(coords[0][1],4)) +
          " -> " + str(round(coords[2][0],4)) + "," + str(round(coords[2][1],4)))
