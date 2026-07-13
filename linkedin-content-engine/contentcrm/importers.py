"""One-time posts.jsonl migration + markdown library import."""
import hashlib
import json
from pathlib import Path

from .platforms import normalise
from .util import dow_bucket, now_iso, parse_when, slot_bucket, slugify, unique_slug

# Curated by reading posts.jsonl, not detected: post-001 and post-002 are the
# same idea expressed short and long (PLAN.md documents the pair and why their
# head-to-head was confounded). A migration is allowed to encode knowledge
# about the specific data it migrates.
SIBLING_GROUPS = [
    {
        "legacy_ids": ["post-001", "post-002"],
        "slug": "ai-jobs-divide",
        "title": "AI replacing jobs / market-vs-confidence divergence",
    }
]


def migrate_posts_jsonl(conn, jsonl_path, cfg):
    rows = [
        json.loads(line)
        for line in Path(jsonl_path).read_text().splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError(f"{jsonl_path} is empty")

    already = [
        r["id"]
        for r in rows
        if conn.execute(
            "SELECT 1 FROM variants WHERE legacy_post_id = ?", (r["id"],)
        ).fetchone()
    ]
    if already:
        raise ValueError(
            f"already migrated ({', '.join(already)} present); refusing to run twice"
        )

    group_of = {}
    for group in SIBLING_GROUPS:
        for legacy_id in group["legacy_ids"]:
            group_of[legacy_id] = group

    summary = {"ideas": 0, "variants": 0, "runs": 0, "metrics": 0, "siblings": []}
    idea_ids = {}  # sibling group slug -> idea id

    for row in rows:
        legacy_id = row["id"]
        posted_at, precision = parse_when(row.get("posted_at"))
        group = group_of.get(legacy_id)

        if group and group["slug"] in idea_ids:
            idea_id = idea_ids[group["slug"]]
        else:
            title = group["title"] if group else row.get("topic") or legacy_id
            slug = unique_slug(conn, group["slug"] if group else slugify(title))
            cur = conn.execute(
                "INSERT INTO ideas (slug, title, source, created_at, notes)"
                " VALUES (?, ?, 'posts.jsonl', ?, ?)",
                (slug, title, posted_at[:10], f"migrated from posts.jsonl {legacy_id}"),
            )
            idea_id = cur.lastrowid
            summary["ideas"] += 1
            if group:
                idea_ids[group["slug"]] = idea_id

        body = row.get("body")
        word_count = row.get("word_count") or (len(body.split()) if body else None)
        variant_notes = "" if body else (
            "body not recorded in posts.jsonl; the live post differed from any"
            " draft file, so nothing was backfilled"
        )
        cur = conn.execute(
            "INSERT INTO variants (idea_id, platform, body, hook_archetype, format,"
            " cta_type, stage, word_count, hashtags, legacy_post_id, created_at, notes)"
            " VALUES (?, 'linkedin', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                idea_id,
                body,
                row.get("hook_archetype"),
                row.get("format"),
                row.get("cta_type"),
                row.get("stage"),
                word_count,
                json.dumps(row.get("hashtags") or []),
                legacy_id,
                posted_at[:10],
                variant_notes,
            ),
        )
        variant_id = cur.lastrowid
        summary["variants"] += 1
        if group:
            summary["siblings"].append(
                {"legacy_id": legacy_id, "variant_id": variant_id, "idea_id": idea_id,
                 "idea_slug": group["slug"]}
            )

        run_notes = row.get("notes") or ""
        if row.get("schedule_slot"):
            run_notes = f"schedule_slot: {row['schedule_slot']}\n{run_notes}".strip()
        if precision == "approx":
            run_notes = f"posted date is approximate (was {row.get('posted_at')})\n{run_notes}".strip()
        cur = conn.execute(
            "INSERT INTO runs (variant_id, platform, posted_at, posted_at_precision,"
            " dow_bucket, slot_bucket, comment_authors, legacy_post_id, created_at, notes)"
            " VALUES (?, 'linkedin', ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                variant_id,
                posted_at,
                precision,
                dow_bucket(posted_at, precision),
                slot_bucket(posted_at, precision, cfg["slots"]),
                json.dumps(row.get("comment_authors") or []),
                legacy_id,
                now_iso(),
                run_notes,
            ),
        )
        run_id = cur.lastrowid
        summary["runs"] += 1

        actuals = row.get("actuals")
        if actuals:
            conn.execute(
                "INSERT INTO metrics (run_id, checkpoint, captured_at, impressions,"
                " reactions, comments, notes) VALUES (?, NULL, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    row.get("checked_at") or posted_at[:10],
                    actuals.get("impressions"),
                    actuals.get("reactions"),
                    actuals.get("comments"),
                    "single legacy snapshot; elapsed age varies, so no checkpoint label",
                ),
            )
            summary["metrics"] += 1

    conn.commit()
    return summary


def _parse_frontmatter(text):
    """Minimal flat 'key: value' frontmatter parser (what mdnotes writes).
    Returns (meta, remaining_body)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return meta, "\n".join(lines[i + 1:])
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip().lower()] = value.strip().strip("'\"")
    return {}, text  # never closed: treat the whole file as body


def _parse_tags(raw):
    if not raw:
        return []
    return [t.strip().strip("'\"") for t in raw.strip("[]").split(",") if t.strip()]


def parse_markdown_file(path):
    """Returns (meta, title, body). Title: frontmatter > first H1 > filename
    (or the page directory for mdnotes' index.md layout)."""
    path = Path(path)
    meta, body = _parse_frontmatter(path.read_text())
    body = body.strip()
    title = meta.get("title")
    if not title:
        for line in body.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                body = body.replace(line, "", 1).strip()
                break
    if not title:
        stem = path.parent.name if path.stem == "index" else path.stem
        title = stem.replace("-", " ").replace("_", " ").strip() or path.stem
    return meta, title, body


def import_markdown_dir(conn, dir_path, platform, cfg):
    """Import every *.md under dir_path as idea + variant. Idempotent by
    source_path + content hash. Never mutates a variant that has runs; an
    edited file whose variant already ran becomes a child variant instead."""
    root = Path(dir_path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"{root} is not a directory")
    platform = normalise(platform)

    summary = {
        "created": [], "updated": [], "rewritten": [],
        "skipped_unchanged": [], "skipped_empty": [],
    }
    for path in sorted(root.rglob("*.md")):
        rel = str(path.relative_to(root))
        meta, title, body = parse_markdown_file(path)
        if not body:
            summary["skipped_empty"].append(rel)
            continue
        content_hash = hashlib.sha256(body.encode()).hexdigest()
        word_count = len(body.split())
        file_platform = normalise(meta.get("platform", platform))
        source_path = str(path)

        existing = conn.execute(
            "SELECT * FROM variants WHERE source_path = ? ORDER BY id DESC LIMIT 1",
            (source_path,),
        ).fetchone()

        if existing:
            if existing["content_hash"] == content_hash:
                summary["skipped_unchanged"].append(rel)
                continue
            has_runs = conn.execute(
                "SELECT 1 FROM runs WHERE variant_id = ? LIMIT 1", (existing["id"],)
            ).fetchone()
            if has_runs:
                conn.execute(
                    "INSERT INTO variants (idea_id, platform, derived_from_variant_id,"
                    " body, hook_archetype, format, cta_type, media_type, stage,"
                    " word_count, hashtags, source_path, content_hash, created_at, notes)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        existing["idea_id"], file_platform, existing["id"], body,
                        meta.get("hook_archetype") or existing["hook_archetype"],
                        meta.get("format") or existing["format"],
                        meta.get("cta_type") or existing["cta_type"],
                        meta.get("media_type") or existing["media_type"],
                        meta.get("stage") or existing["stage"],
                        word_count, existing["hashtags"], source_path, content_hash,
                        now_iso(),
                        f"re-imported from edited {rel}; V{existing['id']} already ran, so this is a new version",
                    ),
                )
                summary["rewritten"].append(rel)
            else:
                conn.execute(
                    "UPDATE variants SET body = ?, content_hash = ?, word_count = ?"
                    " WHERE id = ?",
                    (body, content_hash, word_count, existing["id"]),
                )
                summary["updated"].append(rel)
            continue

        slug = unique_slug(conn, slugify(title))
        cur = conn.execute(
            "INSERT INTO ideas (slug, title, thesis, source, source_path, tags, created_at)"
            " VALUES (?, ?, ?, 'markdown-import', ?, ?, ?)",
            (
                slug, title, meta.get("thesis"), source_path,
                json.dumps(_parse_tags(meta.get("tags"))), now_iso(),
            ),
        )
        conn.execute(
            "INSERT INTO variants (idea_id, platform, body, hook_archetype, format,"
            " cta_type, media_type, stage, word_count, source_path, content_hash, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cur.lastrowid, file_platform, body,
                meta.get("hook_archetype"), meta.get("format"), meta.get("cta_type"),
                meta.get("media_type"), meta.get("stage"),
                word_count, source_path, content_hash, now_iso(),
            ),
        )
        summary["created"].append((rel, slug))

    conn.commit()
    return summary
