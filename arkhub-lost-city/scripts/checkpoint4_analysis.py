#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    print("Checkpoint 4")
    print("Run two parallel streams:")
    print("1. Vision analysis on preview images")
    print("2. Spectral analysis on GeoTIFFs")
    print("Expected outputs:")
    print(ROOT / "data" / "output" / "vision_flags.json")
    print(ROOT / "data" / "output" / "spectral_flags.json")


if __name__ == "__main__":
    main()
