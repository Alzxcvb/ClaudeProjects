#!/usr/bin/env python3
"""
Arkhub Site Discovery Heatmap
Generates candidate 1km² zones for undiscovered Peruvian archaeological sites.

Approach:
  1. KDE density surface from 34 verified sites
  2. Gap analysis: high-density zones with no known site
  3. River corridor scoring (hard-coded south coast rivers)
  4. Composite score → ranked GeoJSON + interactive Folium map

No external APIs required.
"""

import json
import math
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import gaussian_kde
import folium
from folium.plugins import HeatMap
import warnings
warnings.filterwarnings("ignore")

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
SITES_CSV   = ROOT / "data/interim/academic/Peru_academic_verified_coordinates.csv"
INVENTORY   = ROOT / "data/interim/academic/Peru_academic_sites_inventory.csv"
OUT_GEOJSON = ROOT / "data/output/candidate_tiles_scored.geojson"
OUT_MAP     = ROOT / "data/output/discovery_heatmap.html"
OUT_MAP.parent.mkdir(parents=True, exist_ok=True)

# ── South-coast river corridors (approximate centerlines, WGS84) ──────────────
# Each entry: (name, [(lat, lon), ...]) — hand-encoded from geography
RIVERS = [
    ("Rio Grande de Nazca",  [(-14.38,-75.07),(-14.50,-75.12),(-14.62,-75.22),(-14.77,-75.37)]),
    ("Rio Palpa",            [(-14.49,-75.14),(-14.56,-75.19),(-14.65,-75.25)]),
    ("Rio Ingenio",          [(-14.30,-75.10),(-14.43,-75.15),(-14.52,-75.20)]),
    ("Rio Ica",              [(-13.95,-75.45),(-14.07,-75.73),(-14.07,-75.73)]),
    ("Rio Acari",            [(-15.25,-74.55),(-15.43,-74.62),(-15.55,-74.70)]),
    ("Rio Majes / Camana",   [(-16.35,-72.50),(-16.45,-72.80),(-16.62,-72.90)]),
    ("Rio Tambo",            [(-16.90,-71.20),(-17.00,-71.45),(-17.10,-71.68)]),
    ("Rio Osmore / Moquegua",[(-17.00,-70.60),(-17.12,-70.88),(-17.19,-71.00)]),
    ("Rio Ilo",              [(-17.55,-71.20),(-17.65,-71.35),(-17.68,-71.34)]),
    ("Rio Las Trancas",      [(-14.65,-75.28),(-14.72,-75.34),(-14.80,-75.42)]),
    ("Rio Viscas / Nazca S", [(-14.78,-75.10),(-14.83,-75.15),(-14.90,-75.20)]),
]

# ── Grid parameters ──────────────────────────────────────────────────────────
# Focus: Peru's south coast archaeology belt + a northern wing
# ~1 km² at -14°S latitude ≈ 0.009° lat × 0.009° lon
CELL_DEG = 0.009   # ~1 km

STUDY_REGIONS = [
    # (name, lat_min, lat_max, lon_min, lon_max)
    ("Nazca-Palpa Corridor",  -15.20, -13.80, -75.80, -74.50),
    ("Ica-Pisco Coast",       -14.20, -13.50, -76.50, -75.40),
    ("Osmore-Moquegua Valley",-17.30, -16.80, -71.20, -70.50),
    ("North Coast (Lambayeque-La Libertad)", -8.20, -6.50, -80.00, -78.80),
]


def haversine_km(lat1, lon1, lat2, lon2):
    """Distance in km between two WGS84 points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def min_dist_to_river(lat, lon):
    """Return minimum km distance from (lat, lon) to any river segment."""
    min_d = 9999.0
    for _, pts in RIVERS:
        for (rlat, rlon) in pts:
            d = haversine_km(lat, lon, rlat, rlon)
            if d < min_d:
                min_d = d
    return min_d


def load_sites():
    df = pd.read_csv(SITES_CSV)
    df = df.dropna(subset=["latitude", "longitude"])
    df["study_count"] = 1  # default

    # merge study counts
    try:
        inv = pd.read_csv(INVENTORY)
        df = df.merge(inv[["site_name","study_count"]], on="site_name", how="left", suffixes=("","_inv"))
        df["study_count"] = df["study_count_inv"].fillna(1).astype(int)
        df = df.drop(columns=["study_count_inv"])
    except Exception:
        pass

    return df


def build_grid(lat_min, lat_max, lon_min, lon_max):
    lats = np.arange(lat_min, lat_max, CELL_DEG)
    lons = np.arange(lon_min, lon_max, CELL_DEG)
    grid_lats, grid_lons = np.meshgrid(lats, lons, indexing="ij")
    return grid_lats, grid_lons


def score_region(region_name, lat_min, lat_max, lon_min, lon_max, sites_df, kde):
    """Score every 1km² cell in the region and return top candidates."""
    print(f"  Scoring {region_name}...")

    # filter sites to this region (expanded by 2° for KDE context)
    mask = (
        (sites_df["latitude"]  >= lat_min - 2) & (sites_df["latitude"]  <= lat_max + 2) &
        (sites_df["longitude"] >= lon_min - 2) & (sites_df["longitude"] <= lon_max + 2)
    )
    region_sites = sites_df[mask]

    grid_lats, grid_lons = build_grid(lat_min, lat_max, lon_min, lon_max)
    flat_lats = grid_lats.ravel()
    flat_lons = grid_lons.ravel()
    n_cells = len(flat_lats)

    # ── KDE density at each cell ──────────────────────────────────────────────
    all_lats = sites_df["latitude"].values
    all_lons = sites_df["longitude"].values

    # fit KDE over all sites (bandwidth ~100km = 0.9°)
    try:
        kde_func = gaussian_kde(
            np.vstack([all_lats, all_lons]),
            bw_method=0.08   # ~0.9° ≈ 100km at equator
        )
        density = kde_func(np.vstack([flat_lats, flat_lons]))
        density = (density - density.min()) / (density.max() - density.min() + 1e-10)
    except Exception:
        density = np.zeros(n_cells)

    # ── Min distance to any known site ───────────────────────────────────────
    site_lats = region_sites["latitude"].values
    site_lons = region_sites["longitude"].values
    min_site_dist = np.full(n_cells, 999.0)
    for slat, slon in zip(site_lats, site_lons):
        d = np.sqrt(((flat_lats - slat)*111)**2 + ((flat_lons - slon)*111*np.cos(np.radians(slat)))**2)
        min_site_dist = np.minimum(min_site_dist, d)

    # gap score: high density neighbourhood but no known site within 2-15km
    # sweet spot: 2-15km from known sites (close enough to cluster, far enough to be undiscovered)
    gap_score = np.where(
        (min_site_dist >= 2) & (min_site_dist <= 15),
        density * (1 - min_site_dist / 30),
        0.0
    )
    gap_score = np.clip(gap_score, 0, 1)

    # ── River proximity score ─────────────────────────────────────────────────
    print(f"    Computing river proximity for {n_cells} cells...")
    river_dist = np.array([min_dist_to_river(la, lo) for la, lo in zip(flat_lats, flat_lons)])
    # ideal: 0.5-8km from river (close enough for water, not on floodplain)
    river_score = np.where(
        river_dist <= 8,
        1.0 - (river_dist / 8) * 0.5,   # closer = better, capped at 0.5 advantage
        np.exp(-river_dist / 15)         # exponential decay beyond 8km
    )
    river_score = np.clip(river_score, 0, 1)

    # ── Elevation band heuristic (using lat as proxy for coastal zone) ────────
    # South-coast Peru: best sites 0-50km from coast, elevation 50-800m
    # Rough proxy: distance from coast (coast runs ~-76° to -70° lon at this lat)
    coast_lon = -76.5 + (flat_lats + 18) * 0.5   # approximate coast longitude
    dist_from_coast_deg = np.abs(flat_lons - coast_lon)
    elev_score = np.exp(-dist_from_coast_deg / 0.8)   # ~90km optimal depth
    elev_score = np.clip(elev_score, 0, 1)

    # ── Composite score ───────────────────────────────────────────────────────
    composite = (
        0.40 * gap_score      +   # gap near cluster: strongest signal
        0.30 * river_score    +   # near water: settlement requirement
        0.20 * elev_score     +   # coastal zone: most sites are here
        0.10 * density            # raw density context
    )

    # exclude cells with a known site within 0.5km (already discovered)
    composite[min_site_dist < 0.5] = 0.0

    # ── Build candidate feature list ──────────────────────────────────────────
    # top N cells
    top_n = min(80, n_cells)
    top_idx = np.argsort(composite)[::-1][:top_n]

    candidates = []
    for i, idx in enumerate(top_idx):
        score = float(composite[idx])
        if score < 0.05:
            break
        lat_c = float(flat_lats[idx])
        lon_c = float(flat_lons[idx])
        candidates.append({
            "rank": i + 1,
            "region": region_name,
            "lat_center": round(lat_c, 5),
            "lon_center": round(lon_c, 5),
            "composite_score": round(score, 4),
            "gap_score": round(float(gap_score[idx]), 4),
            "river_score": round(float(river_score[idx]), 4),
            "density_score": round(float(density[idx]), 4),
            "nearest_site_km": round(float(min_site_dist[idx]), 2),
            "nearest_river_km": round(float(river_dist[idx]), 2),
            "bbox": [
                round(lon_c - CELL_DEG/2, 6),
                round(lat_c - CELL_DEG/2, 6),
                round(lon_c + CELL_DEG/2, 6),
                round(lat_c + CELL_DEG/2, 6),
            ]
        })

    return candidates, density, flat_lats, flat_lons, composite


def build_geojson(all_candidates):
    features = []
    for c in all_candidates:
        lon, lat = c["lon_center"], c["lat_center"]
        half = CELL_DEG / 2
        coords = [[
            [lon-half, lat-half], [lon+half, lat-half],
            [lon+half, lat+half], [lon-half, lat+half], [lon-half, lat-half]
        ]]
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": coords},
            "properties": {k: v for k, v in c.items() if k != "bbox"}
        })
    return {"type": "FeatureCollection", "features": features}


def build_map(sites_df, all_candidates):
    """Build interactive Folium map."""
    center = [-15.0, -74.5]
    m = folium.Map(location=center, zoom_start=7, tiles="CartoDB dark_matter")

    # ── Known sites ───────────────────────────────────────────────────────────
    site_group = folium.FeatureGroup(name="Known Sites (34 verified)", show=True)
    for _, row in sites_df.iterrows():
        count = int(row.get("study_count", 1))
        radius = max(5, min(20, 4 + count * 0.4))
        color = "#FFD700" if row.get("confidence","") == "high" else "#FFA500"
        popup_html = f"""
            <div style="font-family:monospace;font-size:12px;min-width:200px">
            <b>{row['site_name']}</b><br>
            Studies: {count}<br>
            Coordinates: {row['latitude']:.4f}, {row['longitude']:.4f}<br>
            Status: {row.get('coordinate_status','?')}<br>
            Confidence: {row.get('confidence','?')}
            </div>
        """
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            tooltip=row["site_name"],
            popup=folium.Popup(popup_html, max_width=280)
        ).add_to(site_group)
    site_group.add_to(m)

    # ── KDE heatmap layer ─────────────────────────────────────────────────────
    heat_data = []
    for _, row in sites_df.iterrows():
        count = int(row.get("study_count", 1))
        heat_data.append([row["latitude"], row["longitude"], float(count)])
    HeatMap(
        heat_data,
        name="Academic Study Density Heatmap",
        min_opacity=0.3,
        radius=60,
        blur=40,
        max_zoom=10,
        gradient={0.0: "blue", 0.4: "cyan", 0.65: "yellow", 1.0: "red"},
        show=True
    ).add_to(m)

    # ── River corridors ───────────────────────────────────────────────────────
    river_group = folium.FeatureGroup(name="River Corridors", show=True)
    for rname, pts in RIVERS:
        folium.PolyLine(
            locations=pts,
            color="#4FC3F7",
            weight=2.5,
            opacity=0.7,
            tooltip=rname
        ).add_to(river_group)
    river_group.add_to(m)

    # ── Candidate tiles (colour-coded by score) ───────────────────────────────
    top_candidates = sorted(all_candidates, key=lambda x: x["composite_score"], reverse=True)
    tiers = [
        (0.55, "#FF1744", "Tier 1 — High Priority (score ≥ 0.55)"),
        (0.40, "#FF6D00", "Tier 2 — Medium Priority (0.40–0.55)"),
        (0.25, "#FFD600", "Tier 3 — Low Priority (0.25–0.40)"),
        (0.00, "#69F0AE", "Tier 4 — Marginal (< 0.25)"),
    ]
    tier_groups = {t[2]: folium.FeatureGroup(name=t[2], show=(i < 2)) for i, t in enumerate(tiers)}

    for c in top_candidates:
        score = c["composite_score"]
        color = "#69F0AE"
        tier_name = tiers[-1][2]
        for threshold, clr, name in tiers:
            if score >= threshold:
                color = clr
                tier_name = name
                break

        lon, lat = c["lon_center"], c["lat_center"]
        half = CELL_DEG / 2
        popup_html = f"""
            <div style="font-family:monospace;font-size:11px;min-width:220px">
            <b>Candidate Zone #{c['rank']}</b><br>
            Region: {c['region']}<br>
            Score: <b>{c['composite_score']:.3f}</b><br>
            ├ Gap score: {c['gap_score']:.3f}<br>
            ├ River score: {c['river_score']:.3f}<br>
            └ Density: {c['density_score']:.3f}<br>
            Nearest known site: {c['nearest_site_km']} km<br>
            Nearest river: {c['nearest_river_km']} km<br>
            Center: {lat:.4f}°N, {lon:.4f}°E
            </div>
        """
        folium.Rectangle(
            bounds=[[lat-half, lon-half], [lat+half, lon+half]],
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.25,
            weight=1,
            tooltip=f"#{c['rank']} score={score:.3f} ({c['region']})",
            popup=folium.Popup(popup_html, max_width=260)
        ).add_to(tier_groups[tier_name])

    for g in tier_groups.values():
        g.add_to(m)

    # ── Study region bounding boxes ───────────────────────────────────────────
    region_group = folium.FeatureGroup(name="Study Regions", show=False)
    for rname, la_min, la_max, lo_min, lo_max in STUDY_REGIONS:
        folium.Rectangle(
            bounds=[[la_min, lo_min], [la_max, lo_max]],
            color="#FFFFFF",
            fill=False,
            weight=1,
            dash_array="6",
            tooltip=rname
        ).add_to(region_group)
    region_group.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    # ── Title & legend ────────────────────────────────────────────────────────
    title_html = """
    <div style="position:fixed;top:10px;left:60px;z-index:1000;background:rgba(20,20,20,0.88);
         color:white;padding:12px 16px;border-radius:8px;font-family:monospace;font-size:13px;
         border:1px solid #444;max-width:340px">
      <b style="font-size:15px">🏺 Arkhub: Lost City Discovery Map</b><br>
      <span style="color:#aaa;font-size:11px">NS Archaeology Hackathon · Peru 2026</span><br><br>
      <b>Yellow dots</b> = verified sites (size = study count)<br>
      <b>Heatmap</b> = academic research density<br>
      <b>Blue lines</b> = river corridors<br>
      <b style="color:#FF1744">Red tiles</b> = Tier 1 candidates<br>
      <b style="color:#FF6D00">Orange tiles</b> = Tier 2 candidates<br><br>
      <span style="color:#aaa;font-size:11px">Click any tile for score breakdown</span>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    return m


def main():
    print("Loading site data...")
    sites_df = load_sites()
    print(f"  {len(sites_df)} sites loaded")

    all_candidates = []
    for region_name, la_min, la_max, lo_min, lo_max in STUDY_REGIONS:
        region_candidates, _, _, _, _ = score_region(
            region_name, la_min, la_max, lo_min, lo_max, sites_df, None
        )
        all_candidates.extend(region_candidates)
        print(f"  → {len(region_candidates)} candidates found")

    # global re-rank
    all_candidates.sort(key=lambda x: x["composite_score"], reverse=True)
    for i, c in enumerate(all_candidates):
        c["global_rank"] = i + 1

    print(f"\nTotal candidate tiles: {len(all_candidates)}")
    print("\nTop 10 globally:")
    for c in all_candidates[:10]:
        print(f"  #{c['global_rank']:2d}  score={c['composite_score']:.3f}  "
              f"lat={c['lat_center']:8.4f}  lon={c['lon_center']:9.4f}  "
              f"river={c['nearest_river_km']:5.1f}km  site={c['nearest_site_km']:5.1f}km  "
              f"[{c['region']}]")

    # save GeoJSON
    gj = build_geojson(all_candidates)
    OUT_GEOJSON.write_text(json.dumps(gj, indent=2))
    print(f"\nSaved GeoJSON → {OUT_GEOJSON}")

    # build map
    print("Building interactive map...")
    m = build_map(sites_df, all_candidates)
    m.save(str(OUT_MAP))
    print(f"Saved map    → {OUT_MAP}")
    print("\nDone. Open discovery_heatmap.html in a browser.")


if __name__ == "__main__":
    main()
