#!/usr/bin/env python3
"""Export candidate tiles as MGRS 1km precision CSV."""
import mgrs, json, csv, re
from pathlib import Path

ROOT       = Path(__file__).parent.parent
IN_GEOJSON = ROOT / "data/output/candidate_tiles_v2.geojson"
OUT_CSV    = ROOT / "data/output/candidate_tiles_mgrs.csv"

m = mgrs.MGRS()

def to_mgrs_1km(lat, lon):
    """Return (formatted, compact) MGRS at 1km precision (MGRSPrecision=2)."""
    raw = m.toMGRS(lat, lon, MGRSPrecision=2)
    match = re.match(r'^(\d{1,2})([A-Z])([A-Z]{2})(\d{4})$', raw)
    if not match:
        return raw, raw
    zone_num, zone_band, sq, digits = match.groups()
    easting  = digits[:2]
    northing = digits[2:]
    formatted = zone_num + zone_band + " " + sq + " " + easting + " " + northing
    return formatted, raw

data     = json.loads(IN_GEOJSON.read_text())
features = data["features"]

rows = []
for f in features:
    p = f["properties"]
    fmt, compact = to_mgrs_1km(p["lat_center"], p["lon_center"])
    score = p["composite_score"]
    tier = ("Tier 1 — High Priority"   if score >= 0.60 else
            "Tier 2 — Medium Priority" if score >= 0.45 else
            "Tier 3 — Low Priority"    if score >= 0.30 else
            "Tier 4 — Marginal")
    rows.append({
        "global_rank":      p["global_rank"],
        "mgrs_1km":         fmt,
        "mgrs_compact":     compact,
        "region":           p["region"],
        "tier":             tier,
        "composite_score":  p["composite_score"],
        "gap_score":        p["gap_score"],
        "river_score":      p["river_score"],
        "density_score":    p["density_score"],
        "nearest_site_km":  p["nearest_site_km"],
        "nearest_river_km": p["nearest_river_km"],
        "lat_center":       p["lat_center"],
        "lon_center":       p["lon_center"],
    })

rows.sort(key=lambda x: x["global_rank"])

fields = ["global_rank","mgrs_1km","mgrs_compact","region","tier",
          "composite_score","gap_score","river_score","density_score",
          "nearest_site_km","nearest_river_km","lat_center","lon_center"]

with open(OUT_CSV, "w", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print("Written " + str(len(rows)) + " rows -> " + str(OUT_CSV))
print()
header = "{:>4}  {:16}  {:12}  {:>6}  {:<25}  {}".format(
    "Rank", "MGRS 1km", "Compact", "Score", "Tier", "Region")
print(header)
print("-" * 110)
for r in rows[:15]:
    print("{:>4}  {:16}  {:12}  {:>6.3f}  {:<25}  {}".format(
        r["global_rank"], r["mgrs_1km"], r["mgrs_compact"],
        r["composite_score"], r["tier"], r["region"]))
