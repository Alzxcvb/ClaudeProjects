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
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return {row["site_name"]: row for row in rows}


def load_site_counts() -> dict[str, str]:
    path = ACADEMIC_DIR / "Peru_academic_sites_inventory.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return {row["site_name"]: row["study_count"] for row in rows}


def main() -> None:
    studies_path = ACADEMIC_DIR / "Peru_academic_studies_curated.csv"
    verified = load_verified()
    site_counts = load_site_counts()

    out_rows = []
    with studies_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            sites = [s.strip() for s in row["site_mentions"].split(";") if s.strip()]
            if not sites:
                sites = [""]
            for raw_site in sites:
                site = CANONICAL_MAP.get(raw_site, raw_site)
                verified_row = verified.get(site, {})
                out_rows.append(
                    {
                        "site_name": site,
                        "study_count_for_site": site_counts.get(site, ""),
                        "latitude": verified_row.get("latitude", ""),
                        "longitude": verified_row.get("longitude", ""),
                        "coordinate_status": "verified" if verified_row else "missing",
                        "coordinate_source_name": verified_row.get("source_name", ""),
                        "coordinate_source_url": verified_row.get("source_url", ""),
                        "study_title": row["title"],
                        "study_year": row["year"],
                        "study_doi": row["doi"],
                        "study_source": row["source"],
                        "study_landing_page_url": row["landing_page_url"],
                        "study_pdf_url": row["pdf_url"],
                        "study_authors": row["authors"],
                        "abstract_excerpt": row["abstract_excerpt"],
                    }
                )

    out_rows.sort(key=lambda r: (r["site_name"] == "", r["site_name"].lower(), r["study_title"].lower()))

    out_path = ACADEMIC_DIR / "Peru_academic_master.csv"
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"master_csv: {out_path}")
    print(f"rows: {len(out_rows)}")


if __name__ == "__main__":
    main()
