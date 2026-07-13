"""Resolve what the user typed into a row.

Accepted forms: I3 (idea), V12 (variant), R7 (run), an idea slug or unique
slug prefix, and legacy posts.jsonl ids like post-001 (resolve to the
migrated variant). Bare digits mean: whatever the command expects.
"""
import re


class RefError(LookupError):
    pass


def _fetch(conn, table, row_id):
    return conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()


def resolve_idea(conn, ref):
    ref = ref.strip()
    m = re.fullmatch(r"[Ii](\d+)", ref)
    if m or ref.isdigit():
        row = _fetch(conn, "ideas", int(m.group(1) if m else ref))
        if row:
            return row
        raise RefError(f"no idea with id {ref}")
    row = conn.execute("SELECT * FROM ideas WHERE slug = ?", (ref,)).fetchone()
    if row:
        return row
    rows = conn.execute(
        "SELECT * FROM ideas WHERE slug LIKE ? ORDER BY slug", (ref + "%",)
    ).fetchall()
    if len(rows) == 1:
        return rows[0]
    if len(rows) > 1:
        opts = ", ".join(r["slug"] for r in rows[:6])
        raise RefError(f"'{ref}' matches {len(rows)} ideas: {opts}")
    raise RefError(f"no idea matching '{ref}'")


def resolve_variant(conn, ref):
    ref = ref.strip()
    m = re.fullmatch(r"[Vv](\d+)", ref)
    if m or ref.isdigit():
        row = _fetch(conn, "variants", int(m.group(1) if m else ref))
        if row:
            return row
        raise RefError(f"no variant with id {ref}")
    row = conn.execute(
        "SELECT * FROM variants WHERE legacy_post_id = ?", (ref,)
    ).fetchone()
    if row:
        return row
    raise RefError(f"no variant matching '{ref}' (use V<id> or a legacy post id)")


def latest_run_of_variant(conn, variant_id):
    return conn.execute(
        "SELECT * FROM runs WHERE variant_id = ? ORDER BY posted_at DESC, id DESC LIMIT 1",
        (variant_id,),
    ).fetchone()


def resolve_run(conn, ref=None):
    """R7 -> that run. V12 / post-001 / bare digits -> latest run of that
    variant. None -> the most recently posted run of all."""
    if ref is None:
        row = conn.execute(
            "SELECT * FROM runs ORDER BY posted_at DESC, id DESC LIMIT 1"
        ).fetchone()
        if row:
            return row
        raise RefError("no runs logged yet")
    ref = ref.strip()
    m = re.fullmatch(r"[Rr](\d+)", ref)
    if m:
        row = _fetch(conn, "runs", int(m.group(1)))
        if row:
            return row
        raise RefError(f"no run with id {ref}")
    variant = resolve_variant(conn, ref)
    row = latest_run_of_variant(conn, variant["id"])
    if row:
        return row
    raise RefError(f"variant V{variant['id']} has never run")
