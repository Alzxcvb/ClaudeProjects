"""The recycling queue (`due`) and the open-checkpoints view (`status`).

`due` is the reason this tool exists: ideas whose most recent run on a
platform is older than that platform's cooldown, ranked by how they did last
time, plus the never-run backlog.
"""
from datetime import date, datetime, timedelta

from .scoring import run_performance
from .util import elapsed_hours


def _last_runs_per_idea(conn, platform):
    """idea id -> most recent run row (with idea/variant context) on platform."""
    rows = conn.execute(
        """
        SELECT r.*, v.idea_id AS v_idea_id, v.format AS v_format,
               v.hook_archetype AS v_hook, i.slug AS idea_slug, i.title AS idea_title
        FROM runs r
        JOIN variants v ON v.id = r.variant_id
        JOIN ideas i ON i.id = v.idea_id
        WHERE r.platform = ? AND i.status = 'active'
        ORDER BY r.posted_at, r.id
        """,
        (platform,),
    ).fetchall()
    last = {}
    counts = {}
    for row in rows:  # chronological, so the final assignment wins
        last[row["v_idea_id"]] = row
        counts[row["v_idea_id"]] = counts.get(row["v_idea_id"], 0) + 1
    return last, counts


def due(conn, cfg, platform, today=None):
    today = today or date.today()
    cooldown = cfg["cooldown_days"].get(platform)
    if cooldown is None:
        raise ValueError(f"no cooldown configured for platform '{platform}'")

    last, counts = _last_runs_per_idea(conn, platform)
    due_rows, cooling_rows = [], []
    for idea_id, run in last.items():
        posted = datetime.strptime(run["posted_at"][:10], "%Y-%m-%d").date()
        days_since = (today - posted).days
        perf = run_performance(conn, run, cfg)
        entry = {
            "idea_id": idea_id,
            "idea_slug": run["idea_slug"],
            "idea_title": run["idea_title"],
            "run": run,
            "run_count": counts[idea_id],
            "days_since": days_since,
            "approx": run["posted_at_precision"] == "approx",
            "perf": perf,
            "eligible_on": posted + timedelta(days=cooldown),
        }
        if days_since >= cooldown:
            due_rows.append(entry)
        else:
            cooling_rows.append(entry)

    # Ranked by how they did last time; unmeasured runs sink to the bottom.
    due_rows.sort(
        key=lambda e: -1.0 if e["perf"] is None or e["perf"]["efficiency"] is None
        else e["perf"]["efficiency"],
        reverse=True,
    )
    cooling_rows.sort(key=lambda e: e["eligible_on"])

    never = conn.execute(
        """
        SELECT i.*,
          (SELECT COUNT(*) FROM variants v WHERE v.idea_id = i.id AND v.platform = :p)
            AS platform_variants
        FROM ideas i
        WHERE i.status = 'active' AND i.id NOT IN (
          SELECT v2.idea_id FROM runs r2 JOIN variants v2 ON v2.id = r2.variant_id
          WHERE r2.platform = :p)
        ORDER BY i.created_at DESC, i.id DESC
        """,
        {"p": platform},
    ).fetchall()

    return {"due": due_rows, "cooling": cooling_rows, "never": never,
            "cooldown": cooldown, "platform": platform}


def open_checkpoints(conn, cfg, now=None):
    """Runs from the status window with their checkpoint states:
    done / due / later, plus how many ad-hoc snapshots exist."""
    now = now or datetime.now()
    window_start = (now - timedelta(days=cfg["status_window_days"])).strftime("%Y-%m-%d")
    runs = conn.execute(
        """
        SELECT r.*, i.slug AS idea_slug
        FROM runs r
        JOIN variants v ON v.id = r.variant_id
        JOIN ideas i ON i.id = v.idea_id
        WHERE r.posted_at >= ?
        ORDER BY r.posted_at DESC, r.id DESC
        """,
        (window_start,),
    ).fetchall()

    report = []
    for run in runs:
        elapsed = elapsed_hours(run["posted_at"], ref=now)
        labels = {
            m["checkpoint"]
            for m in conn.execute(
                "SELECT checkpoint FROM metrics WHERE run_id = ?", (run["id"],)
            ).fetchall()
        }
        states = []
        for name, hours in sorted(cfg["checkpoints"].items(), key=lambda kv: kv[1]):
            if name in labels:
                state = "done"
            elif elapsed > hours * 1.5:
                # the moment passed; today's numbers can't say what they were then
                state = "missed"
            elif elapsed >= hours:
                state = "due"
            else:
                state = "later"
            states.append({"name": name, "hours": hours, "state": state})
        has_any_metrics = bool(labels)
        actionable = any(s["state"] in ("due", "later") for s in states)
        # a run whose checkpoints are all settled and which has data is done:
        # don't nag about it. One with no data at all is still worth a snapshot.
        if not actionable and has_any_metrics:
            continue
        report.append({
            "run": run,
            "elapsed_hours": elapsed,
            "checkpoints": states,
            "adhoc_count": sum(1 for l in labels if l is None),
            "no_metrics": not has_any_metrics,
            "anything_due": any(s["state"] == "due" for s in states),
        })
    return report


def auto_checkpoint(cfg, hours_elapsed):
    """Label a snapshot by elapsed time: the nearest configured checkpoint
    whose window (0.6x to 1.5x its nominal hours) contains the elapsed time,
    else None (ad hoc). Windows are wide because Alex logs when he logs, not
    on the exact hour; they derive from config so new checkpoints just work."""
    import math

    candidates = [
        (abs(math.log(hours_elapsed / hours)), name)
        for name, hours in cfg["checkpoints"].items()
        if hours_elapsed > 0 and 0.6 * hours <= hours_elapsed <= 1.5 * hours
    ]
    return min(candidates)[1] if candidates else None
