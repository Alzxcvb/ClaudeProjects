#!/usr/bin/env python3
"""
Filter candidate tiles that fall inside existing urban areas.

Uses GeoNames Peru settlement data (free, no API key) with
population-scaled exclusion radii. Re-exports all three output files:
  candidate_tiles_v2.geojson  → candidate_tiles_v2_filtered.geojson
  candidate_tiles_mgrs.csv   → candidate_tiles_mgrs_filtered.csv
  aoi_survey_areas.geojson   → aoi_survey_areas_filtered.geojson
"""

import json, csv, re, math, zipfile, io, urllib.request
import mgrs as mgrs_lib
from pathlib import Path

ROOT       = Path(__file__).parent.parent
CITIES_CSV = ROOT / "data/raw/peru_cities_geonames.csv"
IN_GEO     = ROOT / "data/output/candidate_tiles_v2.geojson"
OUT_GEO    = ROOT / "data/output/candidate_tiles_v2_filtered.geojson"
OUT_MGRS   = ROOT / "data/output/candidate_tiles_mgrs_filtered.csv"
OUT_AOI    = ROOT / "data/output/aoi_survey_areas_filtered.geojson"
(ROOT / "data/raw").mkdir(parents=True, exist_ok=True)

m = mgrs_lib.MGRS()


# ── Population → exclusion radius (km) ───────────────────────────────────────
def exclusion_radius_km(pop):
    if pop >= 5_000_000: return 22.0   # Lima metro
    if pop >= 1_000_000: return 12.0   # Callao, Arequipa
    if pop >=   500_000: return  8.0   # Trujillo, Chiclayo, Piura, Cusco
    if pop >=   100_000: return  5.0   # Ica, Chimbote, etc.
    if pop >=    50_000: return  3.5
    if pop >=    10_000: return  2.5
    if pop >=     5_000: return  1.8
    return 1.2                          # small towns >= 2,000


# ── Download / load GeoNames cities ──────────────────────────────────────────
def load_cities():
    if CITIES_CSV.exists():
        print("  Loading cities from cache...")
        cities = []
        with open(CITIES_CSV, newline="") as f:
            for row in csv.DictReader(f):
                cities.append({
                    "name": row["name"],
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                    "pop": int(row["pop"]),
                })
        return cities

    print("  Downloading GeoNames Peru data...")
    url = "https://download.geonames.org/export/dump/PE.zip"
    with urllib.request.urlopen(url, timeout=30) as resp:
        zdata = resp.read()

    cities = []
    with zipfile.ZipFile(io.BytesIO(zdata)) as z:
        with z.open("PE.txt") as f:
            for line in f.read().decode("utf-8").split("\n"):
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) < 15:
                    continue
                if parts[6] != "P":        # populated place only
                    continue
                pop = int(parts[14]) if parts[14] else 0
                if pop < 2000:
                    continue
                cities.append({
                    "name": parts[2],
                    "lat": float(parts[4]),
                    "lon": float(parts[5]),
                    "pop": pop,
                })

    # Cache locally
    with open(CITIES_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name","lat","lon","pop"])
        writer.writeheader()
        writer.writerows(cities)
    print("  Cached " + str(len(cities)) + " cities → " + str(CITIES_CSV))
    return cities


def dist_km(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def is_urban(lat, lon, cities):
    """Return (True, city_name, dist_km) if inside any city's exclusion zone."""
    for c in cities:
        d = dist_km(lat, lon, c["lat"], c["lon"])
        r = exclusion_radius_km(c["pop"])
        if d <= r:
            return True, c["name"], round(d, 1), c["pop"]
    return False, None, None, None


# ── MGRS helpers ──────────────────────────────────────────────────────────────
def to_mgrs_1km(lat, lon):
    raw = m.toMGRS(lat, lon, MGRSPrecision=2)
    match = re.match(r'^(\d{1,2})([A-Z])([A-Z]{2})(\d{4})$', raw)
    if not match:
        return raw, raw
    zone_num, zone_band, sq, digits = match.groups()
    fmt = zone_num + zone_band + " " + sq + " " + digits[:2] + " " + digits[2:]
    return fmt, raw

def mgrs_zone(lat, lon):
    raw = m.toMGRS(lat, lon, MGRSPrecision=2)
    match = re.match(r'^(\d{1,2}[A-Z][A-Z]{2})', raw)
    return match.group(1) if match else raw[:5]


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("Loading cities...")
    cities = load_cities()
    print("  " + str(len(cities)) + " settlements loaded")

    print("Loading candidate tiles...")
    data     = json.loads(IN_GEO.read_text())
    features = data["features"]
    print("  " + str(len(features)) + " candidates loaded")

    kept, removed = [], []
    for f in features:
        p   = f["properties"]
        lat = p["lat_center"]
        lon = p["lon_center"]
        urban, city_name, d, pop = is_urban(lat, lon, cities)
        if urban:
            removed.append((p["global_rank"], city_name, d, pop))
        else:
            kept.append(f)

    print("\nRemoved " + str(len(removed)) + " urban tiles:")
    for rank, city, d, pop in sorted(removed, key=lambda x: x[0])[:20]:
        print("  Rank {:>3}  {:>8,.0f} pop  {:>5.1f} km  {}".format(rank, pop, d, city))
    if len(removed) > 20:
        print("  ... and " + str(len(removed) - 20) + " more")

    print("\nKept " + str(len(kept)) + " rural/remote candidates")

    # Re-rank
    kept.sort(key=lambda x: x["properties"]["composite_score"], reverse=True)
    for i, f in enumerate(kept):
        f["properties"]["global_rank"] = i + 1

    # ── Export filtered GeoJSON ───────────────────────────────────────────────
    out_geo = {"type": "FeatureCollection", "features": kept}
    OUT_GEO.write_text(json.dumps(out_geo, indent=2))
    print("\nSaved filtered GeoJSON → " + str(OUT_GEO))

    # ── Export filtered MGRS CSV ──────────────────────────────────────────────
    csv_rows = []
    for f in kept:
        p    = f["properties"]
        lat  = p["lat_center"]
        lon  = p["lon_center"]
        fmt, compact = to_mgrs_1km(lat, lon)
        score = p["composite_score"]
        tier = ("Tier 1 — High Priority"   if score >= 0.60 else
                "Tier 2 — Medium Priority" if score >= 0.45 else
                "Tier 3 — Low Priority"    if score >= 0.30 else
                "Tier 4 — Marginal")
        csv_rows.append({
            "global_rank":      p["global_rank"],
            "mgrs_1km":         fmt,
            "mgrs_compact":     compact,
            "region":           p["region"],
            "tier":             tier,
            "composite_score":  score,
            "gap_score":        p["gap_score"],
            "river_score":      p["river_score"],
            "density_score":    p["density_score"],
            "nearest_site_km":  p["nearest_site_km"],
            "nearest_river_km": p["nearest_river_km"],
            "lat_center":       lat,
            "lon_center":       lon,
        })
    fields = ["global_rank","mgrs_1km","mgrs_compact","region","tier",
              "composite_score","gap_score","river_score","density_score",
              "nearest_site_km","nearest_river_km","lat_center","lon_center"]
    with open(OUT_MGRS, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(csv_rows)
    print("Saved filtered MGRS CSV  → " + str(OUT_MGRS))

    # ── Export filtered AOI GeoJSON ───────────────────────────────────────────
    aoi_features = []
    for f in kept:
        p    = f["properties"]
        lat  = p["lat_center"]
        lon  = p["lon_center"]
        aoi_features.append({
            "type": "Feature",
            "properties": {
                "aoi_name":  "Survey Area " + str(p["global_rank"]),
                "mgrs_zone": mgrs_zone(lat, lon),
            },
            "geometry": f["geometry"]
        })
    OUT_AOI.write_text(json.dumps({"type":"FeatureCollection","features":aoi_features}, indent=2))
    print("Saved filtered AOI GeoJSON → " + str(OUT_AOI))

    # ── Print top 15 ─────────────────────────────────────────────────────────
    print("\nTop 15 candidates (urban-filtered):")
    print("{:>4}  {:16}  {:>6}  {:<25}  {}".format("Rank","MGRS 1km","Score","Tier","Region"))
    print("-" * 100)
    for r in csv_rows[:15]:
        print("{:>4}  {:16}  {:>6.3f}  {:<25}  {}".format(
            r["global_rank"], r["mgrs_1km"], r["composite_score"], r["tier"], r["region"]))


if __name__ == "__main__":
    main()
