#!/usr/bin/env python3
"""Google Maps -> Prospector sourcing layer.

Turns an Apify Google Maps export (CSV or JSON) into a ranked worklist of
small, owner-operated service businesses that match the "Hi I'm Alex" ICP.

WHAT THIS IS (and is NOT):
  - It SOURCES targets. It does not scrape (buy the export from an Apify actor)
    and it does NOT email anyone. Outreach stays LinkedIn-first and personalized,
    run through the existing chrome-mcp flow on the best fits.
  - The output worklist is the intake for that flow: each row carries a
    ready-made LinkedIn people-search link so you can find the owner, then run
    the normal custom-invite send.

WHY a separate layer: per idea-ranker TEST-RUN-017, a custom scraper fails on
build/maintenance and a mass-email blast fights the personalized-video model.
Maps is only the cleanest way to ENUMERATE the ICP by category + city. Buy the
list, rank it here, hand the top fits to the LinkedIn flow.

USAGE:
  python3 src/maps_ingest.py <apify_export.csv|json> --city "Austin, TX"
  python3 src/maps_ingest.py export.csv --city "Austin, TX" --top 25

Recommended Apify actors (pick one, paste its export here):
  - compass/crawler-google-places           (core listing data)
  - lukaskrivka/google-maps-with-contact-details  (adds website-scraped emails/socials)

Outputs (written to prospects/sources/, which is gitignored = local-only PII):
  - maps_candidates_<city>_<date>.csv   full ranked rows
  - maps_worklist_<city>_<date>.md      top-N actionable list for the LinkedIn step
  - maps_seen.csv                       dedup ledger (business|city), never re-imports

Safe to re-run: rows already in maps_seen.csv are skipped, so importing a fresh
or overlapping export only ever adds genuinely new businesses.
"""
import argparse
import csv
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIG = os.path.join(ROOT, "config", "maps_icp.yaml")
OUT_DIR = os.path.join(ROOT, "prospects", "sources")
SEEN_LEDGER = os.path.join(OUT_DIR, "maps_seen.csv")

# Apify actors disagree on column names; map every alias we have seen to one
# canonical field. First non-empty alias wins.
FIELD_ALIASES = {
    "business_name": ["title", "name", "businessName", "business_name"],
    "category": ["categoryName", "category", "categories", "type"],
    "city": ["city", "locality"],
    "state": ["state", "region", "administrativeArea"],
    "website": ["website", "webUrl", "url_website", "site"],
    "phone": ["phone", "phoneUnformatted", "internationalPhoneNumber", "telephone"],
    "maps_url": ["url", "googleMapsUrl", "mapsUrl", "placeUrl"],
    "rating": ["totalScore", "rating", "stars", "averageRating"],
    "reviews": ["reviewsCount", "reviews", "userRatingsTotal", "reviewCount"],
    # email is QUALIFICATION-ONLY. It rides in the CSV (flagged) but never the
    # worklist, and is never used for bulk mail. See no-blast note in the docs.
    "email": ["email", "emails", "contactEmail"],
}

DEFAULT_CONFIG = {
    "icp_categories": [],
    "skip_categories": [],
    "chain_name_flags": [],
    "reviews_min": 4,
    "reviews_max": 600,
    "rating_min": 3.5,
    "require_website": True,
}


def load_config():
    """Read maps_icp.yaml if PyYAML + the file are present; else defaults."""
    cfg = dict(DEFAULT_CONFIG)
    if not os.path.exists(CONFIG):
        return cfg
    try:
        import yaml  # noqa: PyYAML is in requirements.txt
    except ImportError:
        print("warn: PyYAML not installed, using built-in defaults", file=sys.stderr)
        return cfg
    with open(CONFIG) as f:
        loaded = yaml.safe_load(f) or {}
    cfg.update({k: loaded.get(k, cfg[k]) for k in cfg})
    return cfg


def load_rows(path):
    """Load an Apify export as a list of dicts (CSV or JSON array)."""
    if path.lower().endswith(".json"):
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, list) else data.get("items", [])
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def pick(row, field):
    for alias in FIELD_ALIASES[field]:
        v = row.get(alias)
        if v not in (None, "", []):
            # JSON exports sometimes give lists (categories, emails)
            if isinstance(v, list):
                v = v[0] if v else ""
            return str(v).strip()
    return ""


def normalize(row):
    rec = {f: pick(row, f) for f in FIELD_ALIASES}
    rec["rating"] = _to_float(rec["rating"])
    rec["reviews"] = _to_int(rec["reviews"])
    return rec


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _has(haystack, needles):
    h = haystack.lower()
    return any(n.lower() in h for n in needles)


def qualifies(rec, cfg):
    """Return (ok, reason). reason explains the drop when ok is False."""
    cat = rec["category"]
    name = rec["business_name"]
    if not name:
        return False, "no name"
    if _has(cat, cfg["skip_categories"]):
        return False, "skip category"
    if _has(name, cfg["chain_name_flags"]):
        return False, "chain flag"
    if cfg["require_website"] and not rec["website"]:
        return False, "no website"
    if cfg["icp_categories"] and not _has(cat, cfg["icp_categories"]):
        return False, "category off-ICP"
    if rec["reviews"] and rec["reviews"] > cfg["reviews_max"]:
        return False, "too big (reviews > max)"
    if rec["reviews"] and rec["reviews"] < cfg["reviews_min"]:
        return False, "too new (reviews < min)"
    if rec["rating"] and rec["rating"] < cfg["rating_min"]:
        return False, "rating below floor"
    return True, ""


def score(rec, cfg):
    """Higher = better fit for the owner-operator AI pitch."""
    s = 0
    if rec["website"]:
        s += 3
    if cfg["reviews_min"] <= rec["reviews"] <= cfg["reviews_max"]:
        s += 2
    if cfg["icp_categories"] and _has(rec["category"], cfg["icp_categories"]):
        s += 2
    if rec["rating"] >= 4.0:
        s += 1
    if rec["email"]:
        s += 1  # easier to confirm the owner; NOT a reason to email
    return s


def linkedin_finder(rec, city):
    """A Google search scoped to LinkedIn profiles, to find the owner fast."""
    terms = '"{0}" {1} owner OR founder'.format(rec["business_name"], city)
    q = re.sub(r"\s+", "+", "site:linkedin.com/in " + terms).replace('"', "%22")
    return "https://www.google.com/search?q=" + q


def seen_key(name, city):
    return re.sub(r"\s+", " ", (name + "|" + city).lower()).strip()


def load_seen():
    seen = set()
    if os.path.exists(SEEN_LEDGER):
        with open(SEEN_LEDGER, newline="") as f:
            for r in csv.reader(f):
                if r:
                    seen.add(r[0])
    return seen


def append_seen(keys):
    new = not os.path.exists(SEEN_LEDGER)
    with open(SEEN_LEDGER, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["seen_key"])
        for k in keys:
            w.writerow([k])


def slugify_city(city):
    return re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-")


def main():
    ap = argparse.ArgumentParser(description="Rank an Apify Google Maps export into a Prospector worklist.")
    ap.add_argument("export", help="Apify export file (.csv or .json)")
    ap.add_argument("--city", required=True, help='City label, e.g. "Austin, TX"')
    ap.add_argument("--top", type=int, default=30, help="How many to put in the worklist (default 30)")
    ap.add_argument("--date", default=None, help="Override date stamp (YYYY-MM-DD)")
    ap.add_argument("--no-dedup", action="store_true", help="Ignore the seen ledger (still records it)")
    args = ap.parse_args()

    cfg = load_config()
    rows = load_rows(args.export)
    stamp = args.date or datetime.date.today().isoformat()
    os.makedirs(OUT_DIR, exist_ok=True)
    seen = set() if args.no_dedup else load_seen()

    kept, dropped, dup = [], 0, 0
    new_keys = []
    for raw in rows:
        rec = normalize(raw)
        key = seen_key(rec["business_name"], args.city)
        if key in seen:
            dup += 1
            continue
        ok, reason = qualifies(rec, cfg)
        if not ok:
            dropped += 1
            continue
        rec["score"] = score(rec, cfg)
        rec["linkedin_finder"] = linkedin_finder(rec, args.city)
        kept.append(rec)
        new_keys.append(key)
        seen.add(key)

    kept.sort(key=lambda r: (-r["score"], -r["reviews"]))
    append_seen(new_keys)

    if not kept:
        # Nothing new (likely a re-run of an already-imported export). Don't
        # clobber a prior dated worklist with an empty file.
        print("Maps ingest: {0} input, 0 new ({1} off-ICP, {2} already seen). "
              "No output written.".format(len(rows), dropped, dup))
        return

    city_slug = slugify_city(args.city)
    csv_path = os.path.join(OUT_DIR, "maps_candidates_{0}_{1}.csv".format(city_slug, stamp))
    md_path = os.path.join(OUT_DIR, "maps_worklist_{0}_{1}.md".format(city_slug, stamp))

    cols = ["score", "business_name", "category", "rating", "reviews",
            "website", "phone", "maps_url", "linkedin_finder", "email"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in kept:
            w.writerow({c: r.get(c, "") for c in cols})

    write_worklist(md_path, kept[: args.top], args.city, stamp)

    print("Maps ingest: {0} input, {1} kept, {2} off-ICP/dropped, {3} dup-skipped".format(
        len(rows), len(kept), dropped, dup))
    print("  candidates: " + csv_path)
    print("  worklist:   " + md_path + "  (top {0})".format(min(args.top, len(kept))))


def write_worklist(path, recs, city, stamp):
    lines = []
    lines.append("# Maps worklist, {0} ({1})".format(city, stamp))
    lines.append("")
    lines.append("Sourced from a Google Maps export, ranked for the Hi I'm Alex ICP.")
    lines.append("**This is a LinkedIn-first intake. Do not bulk-email these. " +
                 "Use the finder link to locate the owner, then run the normal "
                 "chrome-mcp custom-invite flow.**")
    lines.append("")
    lines.append("For each fit: open the finder link, find the owner's profile, "
                 "fill in their name + slug + a note angle drawn from their real "
                 "headline, then send via the standard flow and log it in SENT_LOG.md.")
    lines.append("")
    for i, r in enumerate(recs, 1):
        rev = "{0}* / {1} reviews".format(r["rating"], r["reviews"]) if r["reviews"] else "no reviews"
        lines.append("## {0}. {1}".format(i, r["business_name"]))
        lines.append("- Category: {0}  |  {1}  |  fit score {2}".format(
            r["category"] or "?", rev, r["score"]))
        if r["website"]:
            lines.append("- Website: {0}".format(r["website"]))
        if r["phone"]:
            lines.append("- Phone: {0}".format(r["phone"]))
        lines.append("- Find owner on LinkedIn: {0}".format(r["linkedin_finder"]))
        lines.append("- [ ] owner name: ______   slug: ______   note angle: ______")
        lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
