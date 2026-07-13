"""Feed generate.py and predict.py from the database.

Returns dicts shaped exactly like the old posts.jsonl rows so the tuned
prompts see the same structure they were tuned on. Missing attributes become
'?' placeholders instead of KeyErrors (posts 013-016 crashed the old loaders).
"""
from .config import db_path, load_config
from .db import connect, latest_metrics


def load_posts_compat(platform=None, require_body=False, config=None):
    cfg = config or load_config()
    platform = platform or cfg["default_platform"]
    conn = connect(db_path(cfg))
    rows = conn.execute(
        """
        SELECT r.id AS run_id, r.legacy_post_id, r.notes AS run_notes,
               v.body, v.format, v.hook_archetype, v.word_count
        FROM runs r JOIN variants v ON v.id = r.variant_id
        WHERE r.platform = ?
        ORDER BY r.posted_at, r.id
        """,
        (platform,),
    ).fetchall()

    posts = []
    for row in rows:
        if require_body and not row["body"]:
            continue
        m = latest_metrics(conn, row["run_id"])
        actuals = None
        if m is not None and m["impressions"] is not None:
            actuals = {
                "impressions": m["impressions"],
                "reactions": m["reactions"] or 0,
                "comments": m["comments"] or 0,
            }
        posts.append({
            "id": row["legacy_post_id"] or f"R{row['run_id']}",
            "format": row["format"] or "?",
            "hook_archetype": row["hook_archetype"] or "?",
            "word_count": row["word_count"] if row["word_count"] is not None else "?",
            "body": row["body"] or "(body not recorded)",
            "actuals": actuals,
            "notes": row["run_notes"] or "",
        })
    conn.close()
    return posts
