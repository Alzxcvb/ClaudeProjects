#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    print("Checkpoint 5")
    print("Merge site map, candidate tiles, vision flags, and spectral flags")
    print("Final outputs should include a ranked shortlist and slide-ready artifacts")
    print("Primary working directory:")
    print(ROOT / "data" / "output")


if __name__ == "__main__":
    main()
