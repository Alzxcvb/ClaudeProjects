#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACADEMIC_DIR = ROOT / "data" / "interim" / "academic"


CANONICAL_MAP = {
    "Nasca": "Nazca lines",
    "Nazca": "Nazca lines",
    "Palpa": "Palpa lines",
    "La Muñaa": "La Muña",
}


def load_verified() -> dict[str, dict[str, str]]:
    path = ACADEMIC_DIR / "Peru_academic_verified_coordinates.csv"
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    return {row["site_name"]: row for row in rows}


def main() -> None:
    studies_path = ACADEMIC_DIR / "Peru_academic_studies_curated.csv"
    verified = load_verified()

    site_stats: dict[str, dict[str, object]] = {}
    with studies_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            title = row["title"]
            doi = row["doi"]
            source = row["source"]
            for raw_site in [s.strip() for s in row["site_mentions"].split(";") if s.strip()]:
                site = CANONICAL_MAP.get(raw_site, raw_site)
                bucket = site_stats.setdefault(
                    site,
                    {
                        "site_name": site,
                        "study_count": 0,
                        "latitude": "",
                        "longitude": "",
                        "coordinate_status": "missing",
                        "coordinate_source": "",
                        "example_study_title": title,
                        "example_study_doi": doi,
                        "example_study_source": source,
                    },
                )
                bucket["study_count"] = int(bucket["study_count"]) + 1
                if not bucket["example_study_title"]:
                    bucket["example_study_title"] = title
                    bucket["example_study_doi"] = doi
                    bucket["example_study_source"] = source

    for site, bucket in site_stats.items():
        if site in verified:
            row = verified[site]
            bucket["latitude"] = row["latitude"]
            bucket["longitude"] = row["longitude"]
            bucket["coordinate_status"] = "verified"
            bucket["coordinate_source"] = row["source_name"]

    rows = sorted(site_stats.values(), key=lambda row: (-int(row["study_count"]), row["site_name"]))
    out_path = ACADEMIC_DIR / "Peru_academic_sites_inventory.csv"
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    verified_count = sum(1 for row in rows if row["coordinate_status"] == "verified")
    print(f"inventory_csv: {out_path}")
    print(f"unique_sites: {len(rows)}")
    print(f"verified_coordinates: {verified_count}")


if __name__ == "__main__":
    main()
