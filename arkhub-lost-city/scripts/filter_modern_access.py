#!/usr/bin/env python3
"""
Filter candidate tiles using a modern-civilization proxy layer.

This supersedes the settlement-only urban filter by combining:
  - GeoNames populated places (required / cached locally)
  - Optional major roads layer
  - Optional postal / courier points
  - Optional airports and ports
  - Optional built-up area polygons

Expected optional inputs live under data/raw/modern_access/ and can be
simple GeoJSON or CSV exports from OSM / Overpass / QGIS.
"""

import csv
import io
import json
import math
import re
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

import mgrs as mgrs_lib
from shapely.geometry import Point, shape

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data/raw"
MODERN_DIR = RAW_DIR / "modern_access"
CITIES_CSV = RAW_DIR / "peru_cities_geonames.csv"

IN_GEO = ROOT / "data/output/candidate_tiles_v2.geojson"
OUT_GEO = ROOT / "data/output/candidate_tiles_v2_filtered.geojson"
OUT_MGRS = ROOT / "data/output/candidate_tiles_mgrs_filtered.csv"
OUT_AOI = ROOT / "data/output/aoi_survey_areas_filtered.geojson"
OUT_REPORT = ROOT / "data/output/modern_access_report.json"

RAW_DIR.mkdir(parents=True, exist_ok=True)
MODERN_DIR.mkdir(parents=True, exist_ok=True)

m = mgrs_lib.MGRS()

ROAD_EXCLUDE_KM = 2.0
SETTLEMENT_NEAR_ROAD_KM = 5.0
POSTAL_EXCLUDE_KM = 5.0
AIRPORT_EXCLUDE_KM = 8.0
PORT_EXCLUDE_KM = 8.0


def exclusion_radius_km(pop):
    if pop >= 5_000_000:
        return 22.0
    if pop >= 1_000_000:
        return 12.0
    if pop >= 500_000:
        return 8.0
    if pop >= 100_000:
        return 5.0
    if pop >= 50_000:
        return 3.5
    if pop >= 10_000:
        return 2.5
    if pop >= 5_000:
        return 1.8
    return 1.2


def dist_km(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def x_km(lon, ref_lat):
    return lon * 111.32 * math.cos(math.radians(ref_lat))


def y_km(lat):
    return lat * 110.57


def point_to_segment_km(px, py, ax, ay, bx, by):
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def iter_linestring_segments(geom):
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])
    if gtype == "LineString":
        yield coords
    elif gtype == "MultiLineString":
        for part in coords:
            yield part
    elif gtype == "Polygon":
        if coords:
            yield coords[0]
    elif gtype == "MultiPolygon":
        for poly in coords:
            if poly:
                yield poly[0]
    elif gtype == "GeometryCollection":
        for g in geom.get("geometries", []):
            yield from iter_linestring_segments(g)


def min_distance_to_geom_km(lat, lon, geom):
    gtype = geom.get("type")
    if gtype == "Point":
        glon, glat = geom["coordinates"]
        return dist_km(lat, lon, glat, glon)
    if gtype == "MultiPoint":
        return min(
            dist_km(lat, lon, pt[1], pt[0])
            for pt in geom.get("coordinates", [])
        )

    px = x_km(lon, lat)
    py = y_km(lat)
    best = float("inf")
    for line in iter_linestring_segments(geom):
        if len(line) == 1:
            glon, glat = line[0]
            best = min(best, dist_km(lat, lon, glat, glon))
            continue
        for i in range(len(line) - 1):
            ax = x_km(line[i][0], lat)
            ay = y_km(line[i][1])
            bx = x_km(line[i + 1][0], lat)
            by = y_km(line[i + 1][1])
            best = min(best, point_to_segment_km(px, py, ax, ay, bx, by))
    return best


def find_named_files(keywords, suffixes):
    matches = []
    for path in MODERN_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in suffixes:
            continue
        tokens = [tok for tok in re.split(r"[^a-z0-9]+", path.stem.lower()) if tok]
        if any(keyword in tokens for keyword in keywords):
            matches.append(path)
    return sorted(matches)


def infer_lat_lon(row):
    lowered = {k.lower(): v for k, v in row.items()}
    lat_keys = ["lat", "latitude", "y", "center_lat"]
    lon_keys = ["lon", "lng", "longitude", "x", "center_lon"]
    lat = next((lowered[k] for k in lat_keys if k in lowered and lowered[k] not in ("", None)), None)
    lon = next((lowered[k] for k in lon_keys if k in lowered and lowered[k] not in ("", None)), None)
    if lat is None or lon is None:
        return None
    try:
        return float(lat), float(lon)
    except ValueError:
        return None


def load_point_csv(path):
    rows = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            coords = infer_lat_lon(row)
            if not coords:
                continue
            lat, lon = coords
            name = (
                row.get("name")
                or row.get("site_name")
                or row.get("title")
                or row.get("id")
                or path.stem
            )
            rows.append({"name": str(name), "lat": lat, "lon": lon})
    return rows


def load_geojson_features(path):
    data = json.loads(path.read_text())
    features = data["features"] if data.get("type") == "FeatureCollection" else [data]
    loaded = []
    for feature in features:
        geom = feature.get("geometry")
        if not geom:
            continue
        props = feature.get("properties") or {}
        loaded.append(
            {
                "name": str(
                    props.get("name")
                    or props.get("ref")
                    or props.get("operator")
                    or props.get("class")
                    or path.stem
                ),
                "geometry": geom,
                "shape": shape(geom),
                "bbox": shape(geom).bounds,
            }
        )
    return loaded


def load_optional_points(label, keywords):
    rows = []
    files = find_named_files(keywords, {".csv", ".geojson", ".json"})
    for path in files:
        if path.suffix.lower() == ".csv":
            rows.extend(load_point_csv(path))
        else:
            for feature in load_geojson_features(path):
                geom = feature["geometry"]
                if geom["type"] == "Point":
                    lon, lat = geom["coordinates"]
                    rows.append({"name": feature["name"], "lat": lat, "lon": lon})
                elif geom["type"] == "MultiPoint":
                    for lon, lat in geom["coordinates"]:
                        rows.append({"name": feature["name"], "lat": lat, "lon": lon})
    print(f"  {label}: {len(rows)} points from {len(files)} file(s)")
    return rows, files


def load_optional_geometries(label, keywords):
    geoms = []
    files = find_named_files(keywords, {".geojson", ".json"})
    for path in files:
        geoms.extend(load_geojson_features(path))
    print(f"  {label}: {len(geoms)} features from {len(files)} file(s)")
    return geoms, files


def load_cities():
    if CITIES_CSV.exists():
        cities = []
        with open(CITIES_CSV, newline="") as f:
            for row in csv.DictReader(f):
                cities.append(
                    {
                        "name": row["name"],
                        "lat": float(row["lat"]),
                        "lon": float(row["lon"]),
                        "pop": int(row["pop"]),
                    }
                )
        return cities

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
                if len(parts) < 15 or parts[6] != "P":
                    continue
                pop = int(parts[14]) if parts[14] else 0
                if pop < 2000:
                    continue
                cities.append(
                    {
                        "name": parts[2],
                        "lat": float(parts[4]),
                        "lon": float(parts[5]),
                        "pop": pop,
                    }
                )

    with open(CITIES_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "lat", "lon", "pop"])
        writer.writeheader()
        writer.writerows(cities)
    return cities


def nearest_city(lat, lon, cities):
    best = None
    best_d = float("inf")
    for city in cities:
        d = dist_km(lat, lon, city["lat"], city["lon"])
        if d < best_d:
            best_d = d
            best = city
    return best, best_d


def inside_city_exclusion(lat, lon, cities):
    for city in cities:
        d = dist_km(lat, lon, city["lat"], city["lon"])
        if d <= exclusion_radius_km(city["pop"]):
            return True, city, d
    return False, None, None


def nearest_point_distance(lat, lon, rows):
    if not rows:
        return None, None
    best = None
    best_d = float("inf")
    for row in rows:
        d = dist_km(lat, lon, row["lat"], row["lon"])
        if d < best_d:
            best_d = d
            best = row
    return best, best_d


def nearest_geom_distance(lat, lon, rows):
    if not rows:
        return None, None
    best = None
    best_d = float("inf")
    for row in rows:
        d = min_distance_to_geom_km(lat, lon, row["geometry"])
        if d < best_d:
            best_d = d
            best = row
    return best, best_d


def build_geom_index(rows, cell_deg=1.0):
    index = defaultdict(list)
    for row in rows:
        minx, miny, maxx, maxy = row["bbox"]
        x0 = math.floor(minx / cell_deg)
        x1 = math.floor(maxx / cell_deg)
        y0 = math.floor(miny / cell_deg)
        y1 = math.floor(maxy / cell_deg)
        for gx in range(x0, x1 + 1):
            for gy in range(y0, y1 + 1):
                index[(gx, gy)].append(row)
    return {"cell_deg": cell_deg, "cells": index, "rows": rows}


def nearest_geom_distance_indexed(lat, lon, index, max_ring=3):
    if not index:
        return None, None
    cell_deg = index["cell_deg"]
    gx = math.floor(lon / cell_deg)
    gy = math.floor(lat / cell_deg)
    candidates = []
    seen = set()
    for ring in range(0, max_ring + 1):
        for x in range(gx - ring, gx + ring + 1):
            for y in range(gy - ring, gy + ring + 1):
                if ring > 0 and abs(x - gx) < ring and abs(y - gy) < ring:
                    continue
                for row in index["cells"].get((x, y), []):
                    ident = id(row)
                    if ident in seen:
                        continue
                    seen.add(ident)
                    candidates.append(row)
        if candidates:
            break
    if not candidates:
        return nearest_geom_distance(lat, lon, index["rows"])
    return nearest_geom_distance(lat, lon, candidates)


def contains_point(lat, lon, rows):
    if not rows:
        return None
    pt = Point(lon, lat)
    for row in rows:
        if row["shape"].contains(pt):
            return row
    return None


def proximity_penalty(distance_km, scale_km):
    if distance_km is None:
        return 0.0
    return math.exp(-distance_km / scale_km)


def compute_modern_access_score(metrics):
    score = (
        0.35 * proximity_penalty(metrics["nearest_settlement_km"], 12.0)
        + 0.30 * proximity_penalty(metrics["nearest_major_road_km"], 8.0)
        + 0.15 * proximity_penalty(metrics["nearest_post_office_km"], 6.0)
        + 0.10 * proximity_penalty(metrics["nearest_airport_km"], 12.0)
        + 0.10 * proximity_penalty(metrics["nearest_port_km"], 12.0)
    )
    return round(min(score, 1.0), 4)


def classify_exclusion(metrics):
    if metrics["inside_built_up_area"]:
        return "built_up_area"
    if metrics["inside_settlement_exclusion"]:
        return "settlement_radius"
    if (
        metrics["nearest_major_road_km"] is not None
        and metrics["nearest_major_road_km"] <= ROAD_EXCLUDE_KM
        and metrics["nearest_settlement_km"] is not None
        and metrics["nearest_settlement_km"] <= SETTLEMENT_NEAR_ROAD_KM
    ):
        return "road_plus_settlement"
    if (
        metrics["nearest_post_office_km"] is not None
        and metrics["nearest_post_office_km"] <= POSTAL_EXCLUDE_KM
    ):
        return "postal_service"
    if (
        metrics["nearest_airport_km"] is not None
        and metrics["nearest_airport_km"] <= AIRPORT_EXCLUDE_KM
    ):
        return "airport_access"
    if (
        metrics["nearest_port_km"] is not None
        and metrics["nearest_port_km"] <= PORT_EXCLUDE_KM
    ):
        return "port_access"
    return None


def to_mgrs_1km(lat, lon):
    raw = m.toMGRS(lat, lon, MGRSPrecision=2)
    match = re.match(r"^(\d{1,2})([A-Z])([A-Z]{2})(\d{4})$", raw)
    if not match:
        return raw, raw
    zone_num, zone_band, sq, digits = match.groups()
    fmt = zone_num + zone_band + " " + sq + " " + digits[:2] + " " + digits[2:]
    return fmt, raw


def mgrs_zone(lat, lon):
    raw = m.toMGRS(lat, lon, MGRSPrecision=2)
    match = re.match(r"^(\d{1,2}[A-Z][A-Z]{2})", raw)
    return match.group(1) if match else raw[:5]


def annotate_feature(feature, metrics, exclusion_reason):
    props = feature["properties"]
    props["nearest_settlement_km"] = round(metrics["nearest_settlement_km"], 2) if metrics["nearest_settlement_km"] is not None else None
    props["nearest_major_road_km"] = round(metrics["nearest_major_road_km"], 2) if metrics["nearest_major_road_km"] is not None else None
    props["nearest_post_office_km"] = round(metrics["nearest_post_office_km"], 2) if metrics["nearest_post_office_km"] is not None else None
    props["nearest_airport_km"] = round(metrics["nearest_airport_km"], 2) if metrics["nearest_airport_km"] is not None else None
    props["nearest_port_km"] = round(metrics["nearest_port_km"], 2) if metrics["nearest_port_km"] is not None else None
    props["nearest_settlement_name"] = metrics["nearest_settlement_name"]
    props["modern_access_score"] = metrics["modern_access_score"]
    props["modern_exclusion_reason"] = exclusion_reason
    props["modern_penalty_factor"] = round(1.0 - min(metrics["modern_access_score"] * 0.85, 0.85), 4)
    props["composite_score_pre_modern_filter"] = props["composite_score"]
    props["composite_score"] = round(props["composite_score"] * props["modern_penalty_factor"], 4)


def main():
    print("Loading settlements...")
    cities = load_cities()
    print(f"  settlements: {len(cities)}")

    print("Loading optional modern-access layers...")
    roads, road_files = load_optional_geometries("major roads", ["road", "roads", "highway", "highways"])
    postal_points, postal_files = load_optional_points("postal/courier", ["post", "posts", "postal", "courier", "couriers", "serpost", "fedex", "dhl", "ups"])
    airport_points, airport_files = load_optional_points("airports", ["airport", "airports", "aerodrome", "aerodromes", "airfield", "airfields"])
    port_points, port_files = load_optional_points("ports", ["ports", "port_", "harbor", "harbour"])
    built_up_areas, built_up_files = load_optional_geometries("built-up polygons", ["urban", "built", "settlement", "landuse"])
    road_index = build_geom_index(roads, cell_deg=1.0) if roads else None

    print("Loading candidate tiles...")
    data = json.loads(IN_GEO.read_text())
    features = data["features"]
    print(f"  candidates: {len(features)}")

    kept = []
    removed = []

    for feature in features:
        props = feature["properties"]
        lat = props["lat_center"]
        lon = props["lon_center"]

        city_hit, city, city_d = inside_city_exclusion(lat, lon, cities)
        nearest_city_row, nearest_city_d = nearest_city(lat, lon, cities)
        _, road_d = nearest_geom_distance_indexed(lat, lon, road_index) if road_index else (None, None)
        _, postal_d = nearest_point_distance(lat, lon, postal_points)
        _, airport_d = nearest_point_distance(lat, lon, airport_points)
        _, port_d = nearest_point_distance(lat, lon, port_points)
        built_up_hit = contains_point(lat, lon, built_up_areas)

        metrics = {
            "inside_built_up_area": built_up_hit is not None,
            "inside_settlement_exclusion": city_hit,
            "nearest_settlement_km": city_d if city_hit else nearest_city_d,
            "nearest_major_road_km": road_d,
            "nearest_post_office_km": postal_d,
            "nearest_airport_km": airport_d,
            "nearest_port_km": port_d,
            "nearest_settlement_name": (city or nearest_city_row or {}).get("name"),
        }
        metrics["modern_access_score"] = compute_modern_access_score(metrics)

        exclusion_reason = classify_exclusion(metrics)
        annotate_feature(feature, metrics, exclusion_reason)

        if exclusion_reason:
            removed.append(
                {
                    "global_rank": props["global_rank"],
                    "reason": exclusion_reason,
                    "nearest_settlement_name": metrics["nearest_settlement_name"],
                    "nearest_settlement_km": round(metrics["nearest_settlement_km"], 2) if metrics["nearest_settlement_km"] is not None else None,
                    "nearest_major_road_km": round(road_d, 2) if road_d is not None else None,
                    "nearest_post_office_km": round(postal_d, 2) if postal_d is not None else None,
                    "modern_access_score": metrics["modern_access_score"],
                }
            )
        else:
            kept.append(feature)

    kept.sort(key=lambda f: f["properties"]["composite_score"], reverse=True)
    for i, feature in enumerate(kept):
        feature["properties"]["global_rank"] = i + 1

    OUT_GEO.write_text(json.dumps({"type": "FeatureCollection", "features": kept}, indent=2))

    csv_rows = []
    for feature in kept:
        props = feature["properties"]
        lat = props["lat_center"]
        lon = props["lon_center"]
        fmt, compact = to_mgrs_1km(lat, lon)
        score = props["composite_score"]
        tier = (
            "Tier 1 -- High Priority"
            if score >= 0.60
            else "Tier 2 -- Medium Priority"
            if score >= 0.45
            else "Tier 3 -- Low Priority"
            if score >= 0.30
            else "Tier 4 -- Marginal"
        )
        csv_rows.append(
            {
                "global_rank": props["global_rank"],
                "mgrs_1km": fmt,
                "mgrs_compact": compact,
                "region": props["region"],
                "tier": tier,
                "composite_score": props["composite_score"],
                "composite_score_pre_modern_filter": props["composite_score_pre_modern_filter"],
                "modern_access_score": props["modern_access_score"],
                "modern_penalty_factor": props["modern_penalty_factor"],
                "gap_score": props["gap_score"],
                "river_score": props["river_score"],
                "density_score": props["density_score"],
                "nearest_site_km": props["nearest_site_km"],
                "nearest_river_km": props["nearest_river_km"],
                "nearest_settlement_km": props["nearest_settlement_km"],
                "nearest_major_road_km": props["nearest_major_road_km"],
                "nearest_post_office_km": props["nearest_post_office_km"],
                "nearest_airport_km": props["nearest_airport_km"],
                "nearest_port_km": props["nearest_port_km"],
                "nearest_settlement_name": props["nearest_settlement_name"],
                "lat_center": lat,
                "lon_center": lon,
            }
        )

    fields = [
        "global_rank",
        "mgrs_1km",
        "mgrs_compact",
        "region",
        "tier",
        "composite_score",
        "composite_score_pre_modern_filter",
        "modern_access_score",
        "modern_penalty_factor",
        "gap_score",
        "river_score",
        "density_score",
        "nearest_site_km",
        "nearest_river_km",
        "nearest_settlement_km",
        "nearest_major_road_km",
        "nearest_post_office_km",
        "nearest_airport_km",
        "nearest_port_km",
        "nearest_settlement_name",
        "lat_center",
        "lon_center",
    ]
    with open(OUT_MGRS, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(csv_rows)

    aoi_features = []
    for feature in kept:
        props = feature["properties"]
        lat = props["lat_center"]
        lon = props["lon_center"]
        aoi_features.append(
            {
                "type": "Feature",
                "properties": {
                    "aoi_name": f"Survey Area {props['global_rank']}",
                    "mgrs_zone": mgrs_zone(lat, lon),
                    "modern_access_score": props["modern_access_score"],
                },
                "geometry": feature["geometry"],
            }
        )
    OUT_AOI.write_text(json.dumps({"type": "FeatureCollection", "features": aoi_features}, indent=2))

    summary = {
        "input_candidates": len(features),
        "kept_candidates": len(kept),
        "removed_candidates": len(removed),
        "optional_layer_files": {
            "roads": [str(p.relative_to(ROOT)) for p in road_files],
            "postal": [str(p.relative_to(ROOT)) for p in postal_files],
            "airports": [str(p.relative_to(ROOT)) for p in airport_files],
            "ports": [str(p.relative_to(ROOT)) for p in port_files],
            "built_up_areas": [str(p.relative_to(ROOT)) for p in built_up_files],
        },
        "removed_by_reason": {},
        "top_removed_examples": sorted(removed, key=lambda x: x["global_rank"])[:20],
    }
    for row in removed:
        reason = row["reason"]
        summary["removed_by_reason"][reason] = summary["removed_by_reason"].get(reason, 0) + 1
    OUT_REPORT.write_text(json.dumps(summary, indent=2))

    print(f"\nRemoved {len(removed)} candidate tile(s)")
    for reason, count in sorted(summary["removed_by_reason"].items()):
        print(f"  {reason:>22}: {count}")
    print(f"Kept {len(kept)} candidate tile(s)")
    print(f"\nSaved filtered GeoJSON -> {OUT_GEO}")
    print(f"Saved filtered MGRS CSV -> {OUT_MGRS}")
    print(f"Saved filtered AOI GeoJSON -> {OUT_AOI}")
    print(f"Saved filter report -> {OUT_REPORT}")

    if not any([road_files, postal_files, airport_files, port_files, built_up_files]):
        print("\nNote: no optional modern-access files found under data/raw/modern_access/")
        print("      Current run used settlements only plus score fields for future layers.")


if __name__ == "__main__":
    main()
