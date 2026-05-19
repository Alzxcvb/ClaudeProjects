"""CLI for the outreach POC."""
from __future__ import annotations
import json
from pathlib import Path

import click
from dotenv import load_dotenv

from . import db
from . import classifier as clf
from . import drafter as drf
from . import reddit_scraper as rs

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT / "samples"


@click.group()
def cli():
    """Hi I'm Alex — outreach POC."""


@cli.command()
@click.option("--limit-per-sub", default=15, show_default=True)
@click.option("--limit-per-keyword", default=5, show_default=True)
def scan(limit_per_sub: int, limit_per_keyword: int):
    """Scrape Reddit (no auth needed) into the prospects table."""
    conn = db.connect()
    inserted = 0
    seen = 0
    rows_for_sample = []
    for row in rs.scan_all(limit_per_sub=limit_per_sub,
                           limit_per_keyword=limit_per_keyword):
        seen += 1
        new_id = db.insert_prospect(conn, row)
        if new_id is not None:
            inserted += 1
            rows_for_sample.append({**row, "id": new_id})
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    (SAMPLES_DIR / "prospects.json").write_text(
        json.dumps(rows_for_sample, indent=2, ensure_ascii=False)
    )
    click.echo(f"\nScan complete. Seen={seen} new={inserted} "
               f"(deduped {seen - inserted}). Sample: samples/prospects.json")


@cli.command()
@click.option("--limit", default=50, show_default=True)
def classify(limit: int):
    """Run the Claude loose-relevance classifier on unclassified prospects."""
    summary = clf.classify_pending(limit=limit)
    click.echo(f"\nClassify complete: {summary}")


@cli.command()
@click.option("--limit", default=25, show_default=True)
def draft(limit: int):
    """Generate personalized email drafts for qualified prospects."""
    summary = drf.draft_pending(limit=limit)
    click.echo(f"\nDraft complete: {summary['drafted']} drafted, "
               f"{summary['errors']} errors. See samples/drafts/.")


@cli.command()
def status():
    """Print pipeline stats."""
    conn = db.connect()
    s = db.stats(conn)
    click.echo(json.dumps(s, indent=2))


@cli.command()
@click.option("--limit-per-sub", default=10, show_default=True)
@click.option("--classify-limit", default=80, show_default=True)
@click.option("--draft-limit", default=20, show_default=True)
def run(limit_per_sub: int, classify_limit: int, draft_limit: int):
    """End-to-end POC pass: scan + classify + draft."""
    click.echo("== SCAN ==")
    ctx = click.get_current_context()
    ctx.invoke(scan, limit_per_sub=limit_per_sub, limit_per_keyword=3)
    click.echo("\n== CLASSIFY ==")
    ctx.invoke(classify, limit=classify_limit)
    click.echo("\n== DRAFT ==")
    ctx.invoke(draft, limit=draft_limit)
    click.echo("\n== STATUS ==")
    ctx.invoke(status)


if __name__ == "__main__":
    cli()
