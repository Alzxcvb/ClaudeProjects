#!/usr/bin/env python3
from __future__ import annotations

import csv
import glob
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACADEMIC_DIR = ROOT / "data" / "interim" / "academic"

SITE_PATTERNS = [
    "Cahuachi",
    "Piramide Naranjada",
    "Palpa",
    "Pinchango Alto",
    "Pinchango Bajo",
    "Nasca",
    "Nazca",
    "Pista",
    "Llipata",
    "Los Molinos",
    "La Mu[añ]a",
    "Jauranga",
    "Pernil Alto",
    "Alto del Molino",
    "Pisco Valley",
    "Huaca Prieta",
    "Kilometer 4",
    "Moquegua",
    "Sama",
    "Osmore Valley",
    "Acari Valley",
    "Machu Picchu",
    "Intihuatana",
    "Kuelap",
    "Chiribaya Baja",
    "Cerro Ba[uú]l",
    "Cerro Mej[ií]a",
    "Yaral",
    "Torata Alta",
    "Chachapoya",
    "Chachapoyas",
    "Pampa Grande",
    "Ica",
    "Paracas Peninsula",
    "Rio Grande de Nazca",
]

EXCLUDE_TITLE_PATTERNS = [
    "encyclopedia",
    "ancient civilizations of peru",
    "andean culture history",
    "intcal",
    "marine09",
    "radiocarbon measurements",
    "prehistoric tuberculosis",
    "marine geomorphometry",
    "anthropocene",
    "iconography",
    "continental margin",
    "nazca plate",
    "clay mineralogy",
    "crustal structures",
    "phytogeography",
    "ecology of the coastal atacama",
    "variation in holocene el niño",
]


def normalize(text: str) -> str:
    return " ".join((text or "").split())


def find_sites(text: str) -> list[str]:
    found: list[str] = []
    for pattern in SITE_PATTERNS:
        if re.search(rf"\b{pattern}\b", text, flags=re.IGNORECASE):
            canonical = (
                pattern.replace("[añ]", "ña")
                .replace("[uú]", "u")
                .replace("[ií]", "i")
            )
            if canonical not in found:
                found.append(canonical)
    return found


def keep_row(row: dict[str, str]) -> tuple[bool, list[str]]:
    title = normalize(row.get("title", ""))
    abstract = normalize(row.get("abstract_excerpt", ""))
    blob = f"{title} {abstract}"
    title_lower = title.lower()

    if any(pattern in title_lower for pattern in EXCLUDE_TITLE_PATTERNS):
        return False, []

    sites = find_sites(blob)
    if sites:
        return True, sites

    archaeology_terms = [
        "archaeological site",
        "archaeological sites",
        "excavations at",
        "field season",
        "survey of a peruvian archaeological site",
        "late intermediate period site",
        "geoglyph",
        "settlement centers",
        "archaeological survey",
        "archaeological excavations",
    ]
    if "peru" in blob.lower() and any(term in blob.lower() for term in archaeology_terms):
        return True, []

    return False, []


def main() -> None:
    input_paths = sorted(glob.glob(str(ACADEMIC_DIR / "*_papers.csv")))
    deduped: dict[str, dict[str, str]] = {}

    for path in input_paths:
        with open(path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                key = (row.get("doi", "").strip().lower() or row.get("title", "").strip().lower())
                if not key:
                    continue
                if key not in deduped:
                    deduped[key] = row

    curated_rows = []
    for row in deduped.values():
        keep, sites = keep_row(row)
        if not keep:
            continue
        curated_rows.append(
            {
                "title": normalize(row.get("title", "")),
                "year": row.get("year", ""),
                "doi": row.get("doi", ""),
                "source": row.get("source", ""),
                "landing_page_url": row.get("landing_page_url", ""),
                "pdf_url": row.get("pdf_url", ""),
                "authors": row.get("authors", ""),
                "site_mentions": "; ".join(sites),
                "abstract_excerpt": normalize(row.get("abstract_excerpt", "")),
            }
        )

    curated_rows.sort(key=lambda row: ((row["site_mentions"] == ""), row["title"].lower()))

    csv_path = ACADEMIC_DIR / "peru_site_studies_curated.csv"
    json_path = ACADEMIC_DIR / "peru_site_studies_curated_summary.json"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(curated_rows[0].keys()))
        writer.writeheader()
        writer.writerows(curated_rows)

    unique_sites = sorted(
        {
            site.strip()
            for row in curated_rows
            for site in row["site_mentions"].split(";")
            if site.strip()
        }
    )
    summary = {
        "paper_count": len(curated_rows),
        "unique_site_mentions": unique_sites,
        "site_count": len(unique_sites),
        "output_csv": str(csv_path),
    }
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=True)

    print(f"curated_csv: {csv_path}")
    print(f"summary_json: {json_path}")
    print(f"paper_count: {len(curated_rows)}")
    print(f"site_count: {len(unique_sites)}")


if __name__ == "__main__":
    main()
