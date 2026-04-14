Modern access filter inputs

`scripts/filter_modern_access.py` will auto-load local files from this folder.

Supported formats:
- `*.geojson` / `*.json` for points, lines, or polygons
- `*.csv` for point layers with `lat`/`lon` or `latitude`/`longitude`

Recommended file names:
- `major_roads.geojson`
- `postal_points.geojson` or `postal_points.csv`
- `airports.geojson` or `airports.csv`
- `ports.geojson` or `ports.csv`
- `built_up_areas.geojson`

File matching is keyword-based, so these names also work:
- roads: `*road*`, `*highway*`
- postal/courier: `*post*`, `*courier*`, `*serpost*`, `*fedex*`, `*dhl*`, `*ups*`
- airports: `*airport*`, `*aerodrome*`, `*airfield*`
- ports: `*port*`, `*harbor*`, `*harbour*`
- built-up polygons: `*urban*`, `*built*`, `*settlement*`, `*landuse*`

Suggested source workflow:
1. Export Peru-only OSM layers from Overpass, Geofabrik, or QGIS.
2. Keep roads limited to major drivable classes.
3. Keep built-up areas as polygons if available.
4. Re-run `python3 scripts/filter_modern_access.py`.
