#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    print("Checkpoint 3")
    print("Read candidate tiles from:")
    print(ROOT / "data" / "output" / "candidate_tiles.geojson")
    print("Write per-tile imagery outputs under:")
    print(ROOT / "data" / "imagery")
    print("Recommended outputs: image.tif, preview.png, metadata.json")


if __name__ == "__main__":
    main()
