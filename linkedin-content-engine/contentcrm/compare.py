"""Comparison with gates that refuse before they lie.

Two runs are comparable only if they share a platform, a day-of-week bucket,
and a time-of-day slot. Anything else is INCONCLUSIVE, said plainly. A gap
under min_effect_pct on the decision metric is NOISE, do not act. This tool
must never produce a confident number the data cannot support.

Snapshots have ages too: impressions accumulate, so a 24h snapshot against a
7d snapshot is not a fair fight. When both runs carry the same checkpoint
label the comparison uses the highest one they share; otherwise it falls back
to each run's latest snapshot and warns when the capture ages differ a lot.
"""
from .scoring import run_performance
from .util import elapsed_hours

CAVEAT = "One run per side. Directional signal, not proof, at this volume."


def _pick_snapshots(conn, cfg, run_a, run_b):
    """(snapshot_a, snapshot_b, note, warning). Prefers the highest checkpoint
    label present on BOTH runs; falls back to latest-per-run."""
    def snaps(run):
        return conn.execute(
            "SELECT * FROM metrics WHERE run_id = ? ORDER BY captured_at, id",
            (run["id"],),
        ).fetchall()

    def by_label(rows):
        out = {}
        for m in rows:  # chronological, so the latest capture per label wins
            if m["checkpoint"]:
                out[m["checkpoint"]] = m
        return out

    snaps_a, snaps_b = snaps(run_a), snaps(run_b)
    if not snaps_a or not snaps_b:
        return (snaps_a[-1] if snaps_a else None, snaps_b[-1] if snaps_b else None,
                None, None)

    labels_a, labels_b = by_label(snaps_a), by_label(snaps_b)
    common = set(labels_a) & set(labels_b) & set(cfg["checkpoints"])
    if common:
        best = max(common, key=lambda name: cfg["checkpoints"][name])
        return labels_a[best], labels_b[best], f"both at the {best} checkpoint", None

    a, b = snaps_a[-1], snaps_b[-1]
    age_a = max(elapsed_hours(run_a["posted_at"], _dt(a["captured_at"])), 1.0)
    age_b = max(elapsed_hours(run_b["posted_at"], _dt(b["captured_at"])), 1.0)
    note = (f"latest snapshots ({age_a / 24:.1f}d and {age_b / 24:.1f}d after posting;"
            " no shared checkpoint)")
    warning = None
    if max(age_a, age_b) / min(age_a, age_b) > 2:
        warning = ("snapshot ages differ a lot; impressions accumulate with age,"
                   " so treat this with suspicion and prefer same-checkpoint logging")
    return a, b, note, warning


def _dt(text):
    from datetime import datetime

    fmt = "%Y-%m-%d %H:%M" if len(text) > 10 else "%Y-%m-%d"
    return datetime.strptime(text, fmt)


def run_context(conn, run):
    """Run row + display labels (idea slug, variant, legacy id)."""
    extra = conn.execute(
        """
        SELECT v.id AS variant_id, v.format, v.hook_archetype, v.legacy_post_id,
               i.slug AS idea_slug
        FROM variants v JOIN ideas i ON i.id = v.idea_id
        WHERE v.id = ?
        """,
        (run["variant_id"],),
    ).fetchone()
    label = f"R{run['id']}"
    if run["legacy_post_id"]:
        label += f" ({run['legacy_post_id']})"
    return {"run": run, "label": label, "variant_id": extra["variant_id"],
            "idea_slug": extra["idea_slug"], "format": extra["format"],
            "hook": extra["hook_archetype"]}


def compare_runs(conn, cfg, run_a, run_b, metric=None):
    metric = metric or cfg.get("decision_metric", "efficiency")
    a, b = run_context(conn, run_a), run_context(conn, run_b)
    result = {"a": a, "b": b, "metric": metric, "gates": [], "reasons": []}

    def gate(name, ok, detail):
        result["gates"].append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            result["reasons"].append(detail)

    gate(
        "platform",
        run_a["platform"] == run_b["platform"],
        f"platform: {run_a['platform']} vs {run_b['platform']}"
        if run_a["platform"] != run_b["platform"]
        else f"platform: both {run_a['platform']}",
    )

    for field, label, why_unknown in (
        ("dow_bucket", "day of week", "approximate date"),
        ("slot_bucket", "time-of-day slot", "no posting time recorded"),
    ):
        va, vb = run_a[field], run_b[field]
        unknown = [c["label"] for c, v in ((a, va), (b, vb)) if v is None]
        if unknown:
            gate(field, False,
                 f"{label} unknown for {' and '.join(unknown)} ({why_unknown})")
        elif va != vb:
            gate(field, False, f"{label}: {va} vs {vb}")
        else:
            gate(field, True, f"{label}: both {va}")

    snap_a, snap_b, snap_note, snap_warning = _pick_snapshots(conn, cfg, run_a, run_b)
    perf_a = run_performance(conn, run_a, cfg, snapshot=snap_a)
    perf_b = run_performance(conn, run_b, cfg, snapshot=snap_b)
    for ctx, perf in ((a, perf_a), (b, perf_b)):
        if perf is None or not perf["impressions"]:
            gate("metrics", False, f"no usable metrics logged for {ctx['label']}")
    a["perf"], b["perf"] = perf_a, perf_b
    result["snapshot_note"] = snap_note
    result["snapshot_warning"] = snap_warning

    if metric == "reach":
        for ctx, run in ((a, run_a), (b, run_b)):
            if ctx["perf"] and ctx["perf"]["reach"] is None:
                gate("reach", False,
                     f"followers_at_post not recorded for {ctx['label']},"
                     " so normalised reach cannot be computed")
    elif metric != "efficiency":
        raise ValueError(f"unknown decision metric '{metric}' (efficiency | reach)")

    if result["reasons"]:
        result["verdict"] = "INCONCLUSIVE"
        return result

    va = perf_a[metric]
    vb = perf_b[metric]
    result["values"] = {"a": va, "b": vb}
    hi, lo = max(va, vb), min(va, vb)
    result["winner"] = "a" if va >= vb else "b"

    if hi == lo == 0:
        result["verdict"] = "NOISE"
        result["gap_pct"] = 0.0
        return result
    if lo == 0:
        result["verdict"] = "WINNER"
        result["gap_pct"] = None  # ratio undefined against zero
        result["zero_loser"] = True
        return result

    gap_pct = (hi - lo) / lo * 100.0
    result["gap_pct"] = gap_pct
    result["verdict"] = "WINNER" if gap_pct >= cfg["min_effect_pct"] else "NOISE"
    return result
