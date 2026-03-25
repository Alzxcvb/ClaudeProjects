#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACADEMIC_DIR = ROOT / "data" / "interim" / "academic"


COORDINATE_MAP = {
    "Nazca lines": {
        "latitude": "-14.697500",
        "longitude": "-75.135000",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Nazca_lines",
        "source_coordinate_text": "14°41′51″S 75°08′06″W",
        "confidence": "high",
        "notes": "Direct site coordinate for the Nazca geoglyph field.",
    },
    "Palpa lines": {
        "latitude": "-14.596568",
        "longitude": "-75.194949",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://commons.wikimedia.org/wiki/Category:Palpa_lines",
        "source_coordinate_text": "14°35′47.64″S 75°11′41.82″W",
        "confidence": "high",
        "notes": "Direct coordinate for the Palpa geoglyph field.",
    },
    "Ica": {
        "latitude": "-14.06666667",
        "longitude": "-75.73333333",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Ica,_Peru",
        "source_coordinate_text": "-14.06666667, -75.73333333",
        "confidence": "high",
        "notes": "City coordinate used for the Ica site mention.",
    },
    "Cahuachi": {
        "latitude": "-14.818611",
        "longitude": "-75.116667",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://commons.wikimedia.org/wiki/Category:Cahuachi",
        "source_coordinate_text": "14°49′07″S 75°07′00″W",
        "confidence": "high",
        "notes": "Direct coordinate for the Cahuachi archaeological complex.",
    },
    "Pinchango Alto": {
        "latitude": "-14.4808333",
        "longitude": "-75.1758333",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://tierra.tutiempo.net/peru/cerro-pinchango-pe047904.html",
        "source_coordinate_text": "14°28'50.99\"S 75°10'32.98\"W",
        "confidence": "medium",
        "notes": "Representative hilltop coordinate for the upper Pinchango Alto site on Cerro Pinchango.",
    },
    "Acari Valley": {
        "latitude": "-15.4311111",
        "longitude": "-74.6158333",
        "geometry_type": "Point",
        "coordinate_status": "representative",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Acar%C3%AD_District",
        "source_coordinate_text": "Representative coordinate for Acari town in the Acari Valley",
        "confidence": "medium",
        "notes": "Valley-level representative point based on Acari town.",
    },
    "Moquegua": {
        "latitude": "-17.2",
        "longitude": "-70.93333333",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Moquegua",
        "source_coordinate_text": "-17.2, -70.93333333",
        "confidence": "high",
        "notes": "City coordinate used for Moquegua site mentions.",
    },
    "Paracas Peninsula": {
        "latitude": "-13.85888889",
        "longitude": "-76.32888889",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Paracas_Peninsula",
        "source_coordinate_text": "-13.85888889, -76.32888889",
        "confidence": "high",
        "notes": "Peninsula coordinate for the Paracas site area.",
    },
    "Rio Grande de Nazca": {
        "latitude": "-14.5201",
        "longitude": "-75.2015",
        "geometry_type": "Point",
        "coordinate_status": "representative",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/R%C3%ADo_Grande_District,_Palpa",
        "source_coordinate_text": "-14.5201, -75.2015",
        "confidence": "medium",
        "notes": "District-level representative coordinate for the Rio Grande de Nazca area.",
    },
    "Huaca Prieta": {
        "latitude": "-7.924",
        "longitude": "-79.307",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Huaca_Prieta",
        "source_coordinate_text": "-7.924, -79.307",
        "confidence": "high",
        "notes": "Direct coordinate for Huaca Prieta.",
    },
    "Los Molinos": {
        "latitude": "-14.5339333",
        "longitude": "-75.2225000",
        "geometry_type": "Point",
        "coordinate_status": "approximate",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Palpa_province",
        "source_coordinate_text": "Approx. 4 km west of Palpa near the confluence of the Rio Grande and Palpa rivers",
        "confidence": "medium",
        "notes": "Approximate site coordinate derived from Palpa province description.",
    },
    "Machu Picchu": {
        "latitude": "-13.16333333",
        "longitude": "-72.54555556",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Machu_Picchu",
        "source_coordinate_text": "-13.16333333, -72.54555556",
        "confidence": "high",
        "notes": "Direct coordinate for Machu Picchu.",
    },
    "Pernil Alto": {
        "latitude": "-14.492",
        "longitude": "-75.216",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://xronos.ch/sites/52722",
        "source_coordinate_text": "014.492° S, 075.216° W",
        "confidence": "high",
        "notes": "Direct coordinate from XRONOS site record for Pernil Alto PAP-266.",
    },
    "Sama": {
        "latitude": "-17.865",
        "longitude": "-70.5621",
        "geometry_type": "Point",
        "coordinate_status": "representative",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Sama_District",
        "source_coordinate_text": "-17.865, -70.5621",
        "confidence": "medium",
        "notes": "District-level representative coordinate for Sama Valley mentions.",
    },
    "Alto del Molino": {
        "latitude": "-13.71000000",
        "longitude": "-76.20000000",
        "geometry_type": "Point",
        "coordinate_status": "representative",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Pisco,_Peru",
        "source_coordinate_text": "-13.71, -76.2",
        "confidence": "medium",
        "notes": "Representative coordinate in the Pisco urban-valley area for Alto del Molino.",
    },
    "Cerro Baul": {
        "latitude": "-17.11211500",
        "longitude": "-70.85881000",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Cerro_Ba%C3%BAl",
        "source_coordinate_text": "17°6′43.614″S 70°51′31.716″W",
        "confidence": "high",
        "notes": "Direct coordinate for Cerro Baul.",
    },
    "Cerro Mejia": {
        "latitude": "-17.095",
        "longitude": "-70.8558",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://mapasamerica.dices.net/peru/mapa.php?id=34003&nombre=Cerro-Mejia",
        "source_coordinate_text": "Latitud: -17.095 Longitud: -70.8558",
        "confidence": "high",
        "notes": "Direct coordinate for Cerro Mejia.",
    },
    "Chachapoya": {
        "latitude": "-6.426295",
        "longitude": "-77.9271134",
        "geometry_type": "Point",
        "coordinate_status": "representative",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Ku%C3%A9lap",
        "source_coordinate_text": "-6.426295, -77.9271134",
        "confidence": "medium",
        "notes": "Representative coordinate using Kuélap, the best-known monumental Chachapoya site.",
    },
    "Chachapoyas": {
        "latitude": "-6.217",
        "longitude": "-77.850",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Chachapoyas,_Peru",
        "source_coordinate_text": "6°13′S 77°51′W",
        "confidence": "high",
        "notes": "City coordinate for Chachapoyas.",
    },
    "Chiribaya Baja": {
        "latitude": "-17.6458583",
        "longitude": "-71.3453139",
        "geometry_type": "Point",
        "coordinate_status": "representative",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Ilo,_Peru",
        "source_coordinate_text": "Representative coordinate near Ilo for coastal Chiribaya Baja",
        "confidence": "medium",
        "notes": "Representative lower-valley coastal coordinate near Ilo for Chiribaya Baja.",
    },
    "Intihuatana": {
        "latitude": "-13.16333333",
        "longitude": "-72.54555556",
        "geometry_type": "Point",
        "coordinate_status": "representative",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Machu_Picchu",
        "source_coordinate_text": "Representative coordinate within Machu Picchu",
        "confidence": "medium",
        "notes": "Representative coordinate for the Intihuatana stone within Machu Picchu.",
    },
    "Jauranga": {
        "latitude": "-14.54662",
        "longitude": "-75.20471",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://mapcarta.com/20221136",
        "source_coordinate_text": "-14.54662, -75.20471",
        "confidence": "high",
        "notes": "Direct coordinate for Jauranga hamlet/site area near Palpa.",
    },
    "Kilometer 4": {
        "latitude": "-17.6458583",
        "longitude": "-71.3453139",
        "geometry_type": "Point",
        "coordinate_status": "representative",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Ilo,_Peru",
        "source_coordinate_text": "Representative coordinate for the Ilo area on the extreme south coast of Peru",
        "confidence": "medium",
        "notes": "Representative coastal coordinate for the Kilometer 4 site in the Ilo area.",
    },
    "Kuelap": {
        "latitude": "-6.426295",
        "longitude": "-77.9271134",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Ku%C3%A9lap",
        "source_coordinate_text": "-6.426295, -77.9271134",
        "confidence": "high",
        "notes": "Direct coordinate for Kuélap.",
    },
    "La Muña": {
        "latitude": "-14.5201",
        "longitude": "-75.2015",
        "geometry_type": "Point",
        "coordinate_status": "representative",
        "coordinate_lookup_url": "https://consultasenlinea.mincetur.gob.pe/fichaInventario/index.aspx?cod_Ficha=245",
        "source_coordinate_text": "Site on the right bank of the Rio Grande valley near Palpa; representative Rio Grande district coordinate",
        "confidence": "medium",
        "notes": "Representative Rio Grande district coordinate for La Muña.",
    },
    "Osmore Valley": {
        "latitude": "-17.20000000",
        "longitude": "-70.93333333",
        "geometry_type": "Point",
        "coordinate_status": "representative",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Osmore_River",
        "source_coordinate_text": "Representative mid-valley coordinate in Moquegua/Osmore drainage",
        "confidence": "medium",
        "notes": "Representative coordinate for the mid Osmore Valley archaeological zone.",
    },
    "Pampa Grande": {
        "latitude": "-6.76256",
        "longitude": "-79.47396",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://mapcarta.com/19733674",
        "source_coordinate_text": "-6.76256, -79.47396",
        "confidence": "high",
        "notes": "Direct coordinate for Pampa Grande archaeological site.",
    },
    "Piramide Naranjada": {
        "latitude": "-14.818611",
        "longitude": "-75.116667",
        "geometry_type": "Point",
        "coordinate_status": "representative",
        "coordinate_lookup_url": "https://www.sciencedirect.com/science/article/abs/pii/S0305440310004474",
        "source_coordinate_text": "Mound within the Cahuachi complex; representative Cahuachi coordinate",
        "confidence": "medium",
        "notes": "Representative coordinate within the Cahuachi complex for Piramide Naranjada.",
    },
    "Pisco Valley": {
        "latitude": "-13.71000000",
        "longitude": "-76.20000000",
        "geometry_type": "Point",
        "coordinate_status": "representative",
        "coordinate_lookup_url": "https://en.wikipedia.org/wiki/Pisco,_Peru",
        "source_coordinate_text": "-13.71, -76.2",
        "confidence": "medium",
        "notes": "Representative coordinate for the Pisco Valley study area.",
    },
    "Pista": {
        "latitude": "-14.5339333",
        "longitude": "-75.1854833",
        "geometry_type": "Point",
        "coordinate_status": "representative",
        "coordinate_lookup_url": "https://www.mdpi.com/2076-3263/8/12/479",
        "source_coordinate_text": "Few kilometers from Palpa city; representative Palpa coordinate",
        "confidence": "medium",
        "notes": "Representative coordinate for the Pista geoglyph near Palpa.",
    },
    "Torata Alta": {
        "latitude": "-17.07666",
        "longitude": "-70.82822",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://mapcarta.com/N3404140596",
        "source_coordinate_text": "-17.07666, -70.82822",
        "confidence": "high",
        "notes": "Direct coordinate for Torata Alta.",
    },
    "Yaral": {
        "latitude": "-17.14944",
        "longitude": "-70.92444",
        "geometry_type": "Point",
        "coordinate_status": "exact",
        "coordinate_lookup_url": "https://mapcarta.com/20250456",
        "source_coordinate_text": "-17.14944, -70.92444",
        "confidence": "high",
        "notes": "Direct coordinate for El Yaral / Yaral.",
    },
}


def load_inventory() -> list[dict[str, str]]:
    path = ACADEMIC_DIR / "Peru_academic_sites_inventory.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_study_urls() -> dict[str, str]:
    out: dict[str, str] = {}
    path = ACADEMIC_DIR / "Peru_academic_studies_curated.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            out[row["title"]] = row["landing_page_url"] or row["pdf_url"]
    return out


def write_geojson(rows: list[dict[str, str]]) -> None:
    features = []
    for row in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": row["geometry_type"],
                    "coordinates": [float(row["longitude"]), float(row["latitude"])],
                },
                "properties": {
                    "site_name": row["site_name"],
                    "coordinate_status": row["coordinate_status"],
                    "source_name": row["source_name"],
                    "source_url": row["source_url"],
                    "coordinate_lookup_url": row["coordinate_lookup_url"],
                    "confidence": row["confidence"],
                    "notes": row["notes"],
                },
            }
        )

    path = ACADEMIC_DIR / "Peru_academic_verified_coordinates.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, indent=2), encoding="utf-8")


def main() -> None:
    inventory_rows = load_inventory()
    study_urls = load_study_urls()

    out_rows: list[dict[str, str]] = []
    missing = []
    for row in inventory_rows:
        site = row["site_name"]
        if site not in COORDINATE_MAP:
            missing.append(site)
            continue
        meta = COORDINATE_MAP[site]
        out_rows.append(
            {
                "site_name": site,
                "latitude": meta["latitude"],
                "longitude": meta["longitude"],
                "geometry_type": meta["geometry_type"],
                "coordinate_status": meta["coordinate_status"],
                "source_name": row["example_study_title"],
                "source_url": study_urls.get(row["example_study_title"], row["example_study_doi"]),
                "coordinate_lookup_url": meta["coordinate_lookup_url"],
                "source_coordinate_text": meta["source_coordinate_text"],
                "confidence": meta["confidence"],
                "notes": meta["notes"],
            }
        )

    if missing:
        raise SystemExit(f"missing coordinate mapping for: {', '.join(sorted(missing))}")

    out_rows.sort(key=lambda item: item["site_name"].lower())
    out_path = ACADEMIC_DIR / "Peru_academic_verified_coordinates.csv"
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    write_geojson(out_rows)
    print(f"verified_csv: {out_path}")
    print(f"rows: {len(out_rows)}")


if __name__ == "__main__":
    main()
