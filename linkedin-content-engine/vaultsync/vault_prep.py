#!/usr/bin/env python3
"""
Prepare the mdnotes swipe-file vault for import into content.db.

Two jobs the existing `./crm import` cannot do:

  1. STRIP  - parse_markdown_file() returns the page body with its Notion
              metadata still attached ("Date:", "Source:", "Posted ...", a bare
              linkedin.com/posts/ URL). Those lines would be published verbatim.
  2. MARK   - pages that carry a linkedin.com/posts/ URL are ALREADY LIVE.
              A plain import records them as never-run, which is how the same
              copy goes out twice inside the 90-day cooldown.

Read-only by default. Writes nothing unless --emit-dir or --write-runs is given.

  python3 vault_prep.py --report
  python3 vault_prep.py --emit-dir ../vault-clean         # clean .md for ./crm import
  python3 vault_prep.py --write-runs --db ../content.db   # backfill runs for live pages
"""
import argparse, hashlib, os, re, sqlite3, sys
from datetime import datetime, timezone

VAULT = os.path.expanduser(
    "~/Notes/notion-import-2026-07-13/alexs-homepage/content-library/"
    "linkedin-career-content/content-for-posting"
)
FOLDERS = ["swipe-file", "swipe-file-posts-left-since-august-14"]
MIN_WORDS = 60

POST_URL_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/posts/[^\s)>\]]+", re.I)
ACTIVITY_RE = re.compile(r"activity[-:](\d{6,})", re.I)
FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.S)
# metadata lines Notion put above the actual post copy
META_LINE_RE = re.compile(
    r"^\s*(?:"
    r"date\s*[:\-]"
    r"|source\s*[:\-]"
    r"|posted(?:\s+on)?\b"
    r"|created(?:\s+on)?\b"
    r"|updated(?:\s+on)?\b"
    r"|https?://\S+$"
    r"|!\[[^\]]*\]\([^)]*\)$"
    r")",
    re.I,
)
HEADING_POST_RE = re.compile(r"^#{1,3}\s*post\b", re.I)


def canonical(slug):
    return re.sub(r"-\d{1,2}-\d{1,2}$", "", re.sub(r"-\d+$", "", slug))


def strip_body(raw):
    """Return (clean_body, post_url_or_None, dropped_line_count)."""
    text = FRONTMATTER_RE.sub("", raw)
    url_match = POST_URL_RE.search(text)
    post_url = url_match.group(0) if url_match else None

    lines = text.split("\n")

    # If the page uses an explicit "# Post" heading, everything after it is the copy.
    for i, line in enumerate(lines):
        if HEADING_POST_RE.match(line.strip()):
            tail = lines[i + 1 :]
            end = len(tail)
            while end > 0:
                s2 = tail[end - 1].strip()
                if not s2 or META_LINE_RE.match(s2) or POST_URL_RE.search(s2):
                    end -= 1
                    continue
                break
            return "\n".join(tail[:end]).strip(), post_url, i + 1 + (len(tail) - end)

    # Otherwise drop leading metadata lines until real prose starts.
    idx = 0
    while idx < len(lines):
        s = lines[idx].strip()
        if not s or META_LINE_RE.match(s) or s.startswith("#"):
            idx += 1
            continue
        break
    kept = lines[idx:]
    # ...and drop trailing metadata; Notion also parks the live URL at the bottom
    end = len(kept)
    while end > 0:
        s = kept[end - 1].strip()
        if not s or META_LINE_RE.match(s) or POST_URL_RE.search(s) or s in {"-", "--", "*"}:
            end -= 1
            continue
        break
    dropped = idx + (len(kept) - end)
    return "\n".join(kept[:end]).strip(), post_url, dropped


def collect():
    pages = {}
    for folder in FOLDERS:
        base = os.path.join(VAULT, folder)
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            path = os.path.join(base, name, "index.md")
            if not os.path.isfile(path):
                continue
            raw = open(path, errors="replace").read()
            if len(raw.split()) < MIN_WORDS:
                continue
            body, url, dropped = strip_body(raw)
            if len(body.split()) < 25:
                continue
            key = canonical(name)
            prev = pages.get(key)
            # prefer the variant that is already live (it carries the URL)
            if prev and prev["post_url"] and not url:
                continue
            pages[key] = {
                "slug": key,
                "title": key.replace("-", " ").strip().title(),
                "body": body,
                "post_url": url,
                "dropped": dropped,
                "src": path,
                "words": len(body.split()),
                "has_image": bool(re.search(r"!\[[^\]]*\]\(", raw)),
            }
    return pages


def report(pages):
    live = [p for p in pages.values() if p["post_url"]]
    never = [p for p in pages.values() if not p["post_url"]]
    imgs = [p for p in never if p["has_image"]]
    print(f"vault           : {VAULT}")
    print(f"distinct pages  : {len(pages)}")
    print(f"already live    : {len(live)}   (carry a linkedin.com/posts/ URL)")
    print(f"never posted    : {len(never)}")
    print(f"  of those, with an image reference: {len(imgs)}")
    print(f"metadata lines stripped, total     : {sum(p['dropped'] for p in pages.values())}")
    med = sorted(p["words"] for p in never)
    if med:
        print(f"never-posted word count, median    : {med[len(med)//2]}")
    print("\n--- sample of 3 cleaned bodies (first 100 chars) ---")
    for p in list(never)[:3]:
        print(f"\n[{p['slug']}]  ({p['words']} words)")
        print("  " + p["body"][:100].replace("\n", " ") + "...")
    dashy = [p for p in never if re.search(r"[\u2014\u2013]|(?<=\w)-(?=\w)|^\s*-\s*$", p["body"], re.M)]
    print(f"\nSTYLE: never-posted pages containing an em dash, en dash, hyphenated word,")
    print(f"       or a bare '-' separator line: {len(dashy)} of {len(never)}")
    print("       These predate the no-dash rule. They need a copy pass before publishing.")
    leaks = [p for p in pages.values() if POST_URL_RE.search(p["body"]) or p["body"].lower().startswith(("date:", "source:"))]
    print(f"\nSAFETY: cleaned bodies still containing metadata or a post URL: {len(leaks)}")
    for p in leaks[:5]:
        print("  !! " + p["slug"])
    return len(leaks)


def is_clean(p):
    b = p["body"]
    return not POST_URL_RE.search(b) and not b.lower().startswith(("date:", "source:"))


def emit(pages, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    quarantine = os.path.join(out_dir, "_needs_manual_review")
    os.makedirs(quarantine, exist_ok=True)
    n = q = 0
    for p in pages.values():
        if p["post_url"]:
            continue  # already live; do not queue it
        if not is_clean(p):
            with open(os.path.join(quarantine, p["slug"] + ".md"), "w") as f:
                f.write(f"---\ntitle: {p['title']}\nsource_path: {p['src']}\nSTATUS: FAILED AUTOMATIC CLEANING, do not import\n---\n\n{p['body']}\n")
            q += 1
            continue
        fn = os.path.join(out_dir, p["slug"] + ".md")
        with open(fn, "w") as f:
            f.write(f"---\ntitle: {p['title']}\nsource_path: {p['src']}\n---\n\n{p['body']}\n")
        n += 1
    print(f"wrote {n} clean never-posted pages to {out_dir}")
    print(f"quarantined {q} that failed automatic cleaning to {quarantine}/ (NOT importable)")
    print("next: ./crm import " + out_dir + " --platform linkedin")


def write_runs(pages, db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    matched = inserted = 0
    now = datetime.now(timezone.utc).isoformat()
    for p in pages.values():
        if not p["post_url"]:
            continue
        h = hashlib.sha256(p["body"].encode()).hexdigest()
        row = cur.execute("SELECT id FROM variants WHERE content_hash=?", (h,)).fetchone()
        if not row:
            continue
        vid = row[0]
        matched += 1
        already = cur.execute("SELECT 1 FROM runs WHERE variant_id=? AND post_url=?", (vid, p["post_url"])).fetchone()
        if already:
            continue
        cur.execute(
            "INSERT INTO runs (variant_id, platform, posted_at, posted_at_precision, post_url, created_at, notes)"
            " VALUES (?,?,?,?,?,?,?)",
            (vid, "linkedin", None, "unknown", p["post_url"], now,
             "backfilled from vault page carrying a live post URL; exact date unknown"),
        )
        inserted += 1
    conn.commit()
    print(f"live vault pages matched to variants: {matched}; runs inserted: {inserted}")
    if matched == 0:
        print("nothing matched - run --emit-dir and ./crm import FIRST, then re-run with --write-runs")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--emit-dir")
    ap.add_argument("--write-runs", action="store_true")
    ap.add_argument("--db", default=os.path.join(os.path.dirname(__file__), "..", "content.db"))
    a = ap.parse_args()
    pages = collect()
    if a.report or not (a.emit_dir or a.write_runs):
        report(pages)
    if a.emit_dir:
        emit(pages, a.emit_dir)
    if a.write_runs:
        write_runs(pages, a.db)


if __name__ == "__main__":
    main()
