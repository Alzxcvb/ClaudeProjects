#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from arkhub.academic_extractor import SearchConfig, run_search


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search academic metadata providers and extract coordinate mentions."
    )
    parser.add_argument(
        "--query",
        required=True,
        help="Study query, for example: Peru archaeology desert geoglyph site coordinates",
    )
    parser.add_argument(
        "--provider",
        action="append",
        choices=["openalex", "crossref"],
        dest="providers",
        help="Repeat to use multiple providers. Defaults to both.",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=25,
        help="Results per page for paginated providers.",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=2,
        help="Number of pages to request from paginated providers.",
    )
    parser.add_argument(
        "--mailto",
        help="Contact email for polite API usage, especially with Crossref.",
    )
    parser.add_argument(
        "--output-prefix",
        help="Short output name. Defaults to a slugified version of the query.",
    )
    parser.add_argument(
        "--min-year",
        type=int,
        help="Optional lower bound on publication year.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = SearchConfig(
        query=args.query,
        providers=args.providers or ["openalex", "crossref"],
        per_page=args.per_page,
        pages=args.pages,
        mailto=args.mailto,
        output_prefix=args.output_prefix or args.query,
        min_year=args.min_year,
    )
    try:
        outputs = run_search(config, ROOT)
    except RuntimeError as exc:
        raise SystemExit(str(exc))
    print("Academic extraction complete")
    for label, path in outputs.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
