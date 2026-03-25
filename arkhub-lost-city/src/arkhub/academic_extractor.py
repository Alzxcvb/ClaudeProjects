from __future__ import annotations

import csv
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests
from requests import RequestException


DECIMAL_PAIR_RE = re.compile(
    r"(?P<lat>[+-]?\d{1,2}\.\d{2,})\s*[,;/ ]\s*(?P<lon>[+-]?\d{1,3}\.\d{2,})"
)

DMS_PAIR_RE = re.compile(
    r"(?P<lat_deg>\d{1,2})[°\s]+(?P<lat_min>\d{1,2})['\s]+(?P<lat_sec>\d{1,2}(?:\.\d+)?)?[\"]?\s*(?P<lat_dir>[NS])"
    r"[\s,;/]+"
    r"(?P<lon_deg>\d{1,3})[°\s]+(?P<lon_min>\d{1,2})['\s]+(?P<lon_sec>\d{1,2}(?:\.\d+)?)?[\"]?\s*(?P<lon_dir>[EW])",
    re.IGNORECASE,
)

TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class SearchConfig:
    query: str
    providers: list[str]
    per_page: int = 25
    pages: int = 2
    mailto: str | None = None
    output_prefix: str = "study"
    min_year: int | None = None


def build_session(mailto: str | None = None) -> requests.Session:
    session = requests.Session()
    user_agent = "arkhub-academic-extractor/0.1"
    if mailto:
        user_agent = f"{user_agent} ({mailto})"
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }
    )
    return session


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return text or "study"


def invert_abstract(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""
    tokens: list[tuple[int, str]] = []
    for word, positions in index.items():
        for position in positions:
            tokens.append((position, word))
    tokens.sort(key=lambda item: item[0])
    return " ".join(word for _, word in tokens)


def strip_tags(text: str | None) -> str:
    if not text:
        return ""
    return html.unescape(TAG_RE.sub(" ", text)).strip()


def extract_year(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        match = re.search(r"\b(19|20)\d{2}\b", value)
        if match:
            return int(match.group(0))
    return None


def dms_to_decimal(degrees: str, minutes: str, seconds: str | None, direction: str) -> float:
    value = int(degrees) + int(minutes) / 60.0 + (float(seconds) if seconds else 0.0) / 3600.0
    if direction.upper() in {"S", "W"}:
        value *= -1
    return round(value, 6)


def extract_coordinate_mentions(text: str) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    if not text:
        return mentions

    for match in DECIMAL_PAIR_RE.finditer(text):
        lat = float(match.group("lat"))
        lon = float(match.group("lon"))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            mentions.append(
                {
                    "match_text": match.group(0),
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "format": "decimal",
                }
            )

    for match in DMS_PAIR_RE.finditer(text):
        lat = dms_to_decimal(
            match.group("lat_deg"),
            match.group("lat_min"),
            match.group("lat_sec"),
            match.group("lat_dir"),
        )
        lon = dms_to_decimal(
            match.group("lon_deg"),
            match.group("lon_min"),
            match.group("lon_sec"),
            match.group("lon_dir"),
        )
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            mentions.append(
                {
                    "match_text": match.group(0),
                    "lat": lat,
                    "lon": lon,
                    "format": "dms",
                }
            )

    unique: list[dict[str, Any]] = []
    seen: set[tuple[float, float, str]] = set()
    for mention in mentions:
        key = (mention["lat"], mention["lon"], mention["format"])
        if key not in seen:
            seen.add(key)
            unique.append(mention)
    return unique


def excerpt(text: str, limit: int = 1000) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3] + "..."


def normalize_openalex_work(item: dict[str, Any]) -> dict[str, Any]:
    abstract = invert_abstract(item.get("abstract_inverted_index"))
    doi = item.get("doi") or ""
    if doi.startswith("https://doi.org/"):
        doi = doi.removeprefix("https://doi.org/")
    return {
        "provider": "openalex",
        "provider_id": item.get("id", ""),
        "title": item.get("display_name", ""),
        "year": item.get("publication_year"),
        "doi": doi,
        "source": ((item.get("primary_location") or {}).get("source") or {}).get("display_name", ""),
        "landing_page_url": (item.get("primary_location") or {}).get("landing_page_url", ""),
        "pdf_url": (item.get("primary_location") or {}).get("pdf_url", ""),
        "authors": "; ".join(
            author.get("author", {}).get("display_name", "")
            for author in item.get("authorships", [])
            if author.get("author", {}).get("display_name")
        ),
        "abstract": abstract,
        "raw": item,
    }


def normalize_crossref_work(item: dict[str, Any]) -> dict[str, Any]:
    titles = item.get("title") or [""]
    container = item.get("container-title") or [""]
    doi = item.get("DOI") or ""
    authors = []
    for author in item.get("author", []):
        name = " ".join(part for part in [author.get("given"), author.get("family")] if part)
        if name:
            authors.append(name)
    issued = item.get("issued", {}).get("date-parts", [[]])
    year = issued[0][0] if issued and issued[0] else None
    return {
        "provider": "crossref",
        "provider_id": doi,
        "title": titles[0],
        "year": year,
        "doi": doi,
        "source": container[0],
        "landing_page_url": (item.get("URL") or ""),
        "pdf_url": "",
        "authors": "; ".join(authors),
        "abstract": strip_tags(item.get("abstract", "")),
        "raw": item,
    }


def search_openalex(session: requests.Session, config: SearchConfig) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    base_url = "https://api.openalex.org/works"
    for page in range(1, config.pages + 1):
        params = {
            "search": config.query,
            "per-page": config.per_page,
            "page": page,
            "select": ",".join(
                [
                    "id",
                    "doi",
                    "display_name",
                    "publication_year",
                    "primary_location",
                    "authorships",
                    "abstract_inverted_index",
                ]
            ),
        }
        response = session.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        for item in payload.get("results", []):
            work = normalize_openalex_work(item)
            if config.min_year and work["year"] and work["year"] < config.min_year:
                continue
            results.append(work)
    return results


def search_crossref(session: requests.Session, config: SearchConfig) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    base_url = "https://api.crossref.org/works"
    rows = min(config.per_page * config.pages, 100)
    params = {
        "query.bibliographic": config.query,
        "rows": rows,
    }
    if config.mailto:
        params["mailto"] = config.mailto
    response = session.get(base_url, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    for item in payload.get("message", {}).get("items", []):
        work = normalize_crossref_work(item)
        if config.min_year and work["year"] and work["year"] < config.min_year:
            continue
        results.append(work)
    return results


def dedupe_works(works: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for work in works:
        key = work["doi"].lower().strip() or work["title"].lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(work)
    return deduped


def enrich_with_coordinates(works: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    paper_rows: list[dict[str, Any]] = []
    mention_rows: list[dict[str, Any]] = []
    for work in works:
        text_blob = " ".join(
            part for part in [work.get("title", ""), work.get("abstract", "")] if part
        )
        mentions = extract_coordinate_mentions(text_blob)
        paper_rows.append(
            {
                "provider": work["provider"],
                "title": work["title"],
                "year": work["year"],
                "doi": work["doi"],
                "source": work["source"],
                "landing_page_url": work["landing_page_url"],
                "pdf_url": work["pdf_url"],
                "authors": work["authors"],
                "coordinate_mentions": len(mentions),
                "abstract_excerpt": excerpt(work["abstract"]),
            }
        )
        for mention in mentions:
            mention_rows.append(
                {
                    "provider": work["provider"],
                    "title": work["title"],
                    "year": work["year"],
                    "doi": work["doi"],
                    "source": work["source"],
                    "landing_page_url": work["landing_page_url"],
                    "lat": mention["lat"],
                    "lon": mention["lon"],
                    "format": mention["format"],
                    "match_text": mention["match_text"],
                }
            )
    return paper_rows, mention_rows


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_parent(path)
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write("")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run_search(config: SearchConfig, root: Path) -> dict[str, Path]:
    session = build_session(config.mailto)
    all_works: list[dict[str, Any]] = []

    try:
        if "openalex" in config.providers:
            all_works.extend(search_openalex(session, config))
        if "crossref" in config.providers:
            all_works.extend(search_crossref(session, config))
    except RequestException as exc:
        raise RuntimeError(
            "Academic provider request failed. Check network access, provider availability, or try a smaller query."
        ) from exc

    deduped = dedupe_works(all_works)
    paper_rows, mention_rows = enrich_with_coordinates(deduped)

    slug = slugify(config.output_prefix)
    raw_path = root / "data" / "raw" / "academic" / f"{slug}_works.json"
    papers_csv = root / "data" / "interim" / "academic" / f"{slug}_papers.csv"
    mentions_csv = root / "data" / "interim" / "academic" / f"{slug}_coordinate_mentions.csv"
    summary_json = root / "data" / "interim" / "academic" / f"{slug}_summary.json"

    raw_payload = {
        "query": config.query,
        "providers": config.providers,
        "count": len(deduped),
        "works": [
            {
                key: value
                for key, value in work.items()
                if key != "raw"
            }
            for work in deduped
        ],
    }
    summary = {
        "query": config.query,
        "providers": config.providers,
        "paper_count": len(paper_rows),
        "coordinate_mention_count": len(mention_rows),
        "papers_with_coordinates": sum(1 for row in paper_rows if row["coordinate_mentions"] > 0),
        "output_files": {
            "raw_json": str(raw_path),
            "papers_csv": str(papers_csv),
            "coordinate_mentions_csv": str(mentions_csv),
        },
    }

    write_json(raw_path, raw_payload)
    write_csv(papers_csv, paper_rows)
    write_csv(mentions_csv, mention_rows)
    write_json(summary_json, summary)

    return {
        "raw_json": raw_path,
        "papers_csv": papers_csv,
        "coordinate_mentions_csv": mentions_csv,
        "summary_json": summary_json,
    }


def build_openalex_url(query: str, per_page: int, page: int = 1) -> str:
    return (
        "https://api.openalex.org/works"
        f"?search={quote_plus(query)}&per-page={per_page}&page={page}"
    )


def build_crossref_url(query: str, rows: int, mailto: str | None = None) -> str:
    url = f"https://api.crossref.org/works?query.bibliographic={quote_plus(query)}&rows={rows}"
    if mailto:
        url += f"&mailto={quote_plus(mailto)}"
    return url
