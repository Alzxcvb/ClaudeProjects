from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
IMAGERY_DIR = DATA_DIR / "imagery"

SITES_PATH = OUTPUT_DIR / "sites_wgs84.geojson"
CANDIDATE_TILES_PATH = OUTPUT_DIR / "candidate_tiles.geojson"
IMAGERY_INDEX_PATH = IMAGERY_DIR / "index.json"
