#!/usr/bin/env python3
"""Log a LinkedIn post's actuals to posts.jsonl.

Update an existing post's metrics:
    python log.py post-007 --impressions 164 --reactions 6 --comments 5

Add a new post (auto-creates entry if id is unknown):
    python log.py post-008 --new \\
        --posted-at 2026-06-04 \\
        --topic "What 90 minutes with me actually looks like" \\
        --body-file ../hi-im-alex/marketing/post-13.txt \\
        --stage 4 \\
        --format short-punchy \\
        --hook contrarian-take \\
        --impressions 100 --reactions 2 --comments 1

Just bump a metric:
    python log.py post-005 --impressions 280       # leaves reactions/comments alone

List all posts + their metrics:
    python log.py --list
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
POSTS_PATH = ROOT / "posts.jsonl"


def load():
    if not POSTS_PATH.exists():
        return []
    return [json.loads(l) for l in POSTS_PATH.read_text().splitlines() if l.strip()]


def save(posts):
    with POSTS_PATH.open("w") as f:
        for p in posts:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")


def cmd_list(posts):
    if not posts:
        print("(no posts logged yet)")
        return
    print(f"{'ID':<10} {'Posted':<12} {'Stage':<6} {'Imp':>5} {'Rxn':>4} {'Com':>4}  Topic")
    print("-" * 90)
    for p in posts:
        a = p.get("actuals") or {}
        imp = a.get("impressions", "—")
        rxn = a.get("reactions", "—")
        com = a.get("comments", "—")
        topic = (p.get("topic") or "")[:50]
        print(f"{p['id']:<10} {p.get('posted_at', '—'):<12} {p.get('stage', '—'):<6} {imp:>5} {rxn:>4} {com:>4}  {topic}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id", nargs="?", help="Post ID (e.g. post-007)")
    ap.add_argument("--list", action="store_true", help="List all posts and exit")
    ap.add_argument("--new", action="store_true", help="Create new post if id doesn't exist")
    ap.add_argument("--impressions", type=int)
    ap.add_argument("--reactions", type=int)
    ap.add_argument("--comments", type=int)
    ap.add_argument("--posted-at", help="YYYY-MM-DD (required with --new)")
    ap.add_argument("--topic", help="One-line topic (required with --new)")
    ap.add_argument("--body", help="Post body text")
    ap.add_argument("--body-file", help="Path to file containing post body")
    ap.add_argument("--stage", type=int, choices=[1, 2, 3, 4], help="Funnel stage")
    ap.add_argument("--format", default="short-punchy", help="short-punchy | long-form | listicle")
    ap.add_argument("--hook", help="hook_archetype: contrarian-take | stat-shock | story-open | observation | x-vs-y | etc.")
    ap.add_argument("--cta", default="engagement-question", help="cta_type")
    ap.add_argument("--hashtags", help="Comma-separated, e.g. #ClaudeAI,#SmallBusiness")
    ap.add_argument("--schedule-slot", help="e.g. 'Jun-10 / post-07.txt'")
    ap.add_argument("--note", help="Append a dated note")
    args = ap.parse_args()

    print(
        "[log.py] LEGACY: this writes posts.jsonl only, which nothing reads anymore.\n"
        "[log.py] The database (content.db) is the source of truth now: use ./crm log",
        file=sys.stderr,
    )

    posts = load()

    if args.list:
        cmd_list(posts)
        return

    if not args.id:
        ap.error("post id required (or use --list)")

    found = next((p for p in posts if p["id"] == args.id), None)

    if found is None:
        if not args.new:
            print(f"[log] post {args.id} not found. Use --new to create.", file=sys.stderr)
            sys.exit(1)
        if not args.posted_at or not args.topic:
            ap.error("--new requires --posted-at and --topic")
        body = args.body
        if args.body_file:
            body = Path(args.body_file).read_text().strip()
        if not body:
            ap.error("--new requires --body or --body-file")
        hashtags = []
        if args.hashtags:
            hashtags = [h.strip() for h in args.hashtags.split(",") if h.strip()]
        found = {
            "id": args.id,
            "posted_at": args.posted_at,
            "checked_at": date.today().isoformat(),
            "stage": args.stage,
            "schedule_slot": args.schedule_slot,
            "topic": args.topic,
            "format": args.format,
            "hook_archetype": args.hook,
            "word_count": len(body.split()),
            "body": body,
            "hashtags": hashtags,
            "cta_type": args.cta,
            "actuals": None,
            "comment_authors": [],
            "notes": "",
        }
        posts.append(found)

    if any(x is not None for x in (args.impressions, args.reactions, args.comments)):
        if found.get("actuals") is None:
            found["actuals"] = {}
        if args.impressions is not None:
            found["actuals"]["impressions"] = args.impressions
        if args.reactions is not None:
            found["actuals"]["reactions"] = args.reactions
        if args.comments is not None:
            found["actuals"]["comments"] = args.comments
        found["checked_at"] = date.today().isoformat()

    if args.note:
        prev = found.get("notes", "")
        sep = "\n" if prev else ""
        found["notes"] = f"{prev}{sep}[{date.today()}] {args.note}"

    save(posts)
    print(json.dumps(found, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
