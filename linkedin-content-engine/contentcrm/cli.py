"""crm: the daily terminal surface.

Morning:  ./crm due            what should I post today?
          ./crm show V12 --body | pbcopy
          (you post by hand; the tool never posts)
          ./crm ran V12 --followers 520
Evening:  ./crm status         which runs need metrics right now?
          ./crm log -i 210 -r 5 -c 2
"""
import argparse
import json
import sys
from datetime import datetime

from . import ROOT
from .compare import CAVEAT, compare_runs, run_context
from .config import CONFIG_PATH, db_path, load_config, write_default_config
from .db import connect
from .importers import import_markdown_dir, migrate_posts_jsonl
from .platforms import entry_hints, normalise
from .queue import auto_checkpoint, due, open_checkpoints
from .refs import RefError, latest_run_of_variant, resolve_idea, resolve_run, resolve_variant
from .scoring import run_performance
from .util import (dow_bucket, elapsed_hours, fmt_num, now_iso, parse_when,
                   slot_bucket, slugify, unique_slug)

METRIC_FLAGS = ["impressions", "reactions", "comments", "reposts", "saves",
                "link_clicks", "profile_visits", "bookings"]


def _when_label(run):
    label = run["posted_at"]
    if run["posted_at_precision"] == "approx":
        label = "~" + label
    parts = [p for p in (run["dow_bucket"], run["slot_bucket"]) if p]
    if parts:
        label += f" ({' '.join(parts)})"
    elif run["posted_at_precision"] != "minute":
        label += " (time unknown)"
    return label


def _perf_cells(perf):
    if perf is None:
        return "no metrics", "", ""
    return (f"imp {perf['impressions']}", f"eff {fmt_num(perf['efficiency'])}",
            f"reach {fmt_num(perf['reach'], 2)}")


def _read_body(args):
    if getattr(args, "body", None):
        return args.body
    if getattr(args, "body_file", None):
        if args.body_file == "-":
            return sys.stdin.read().strip()
        from pathlib import Path
        return Path(args.body_file).read_text().strip()
    raise ValueError("give the text with --body or --body-file (use '-' for stdin)")


# ---------------------------------------------------------------- daily

def cmd_due(conn, cfg, args):
    platform = normalise(args.platform or cfg["default_platform"])
    q = due(conn, cfg, platform)
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"WHAT TO POST · {platform} · cooldown {q['cooldown']}d · {today}\n")

    print("DUE FOR RETEST (past cooldown, ranked by last efficiency)")
    if not q["due"]:
        print("  nothing is past cooldown yet")
    for e in q["due"]:
        run = e["run"]
        eff = fmt_num(e["perf"]["efficiency"]) if e["perf"] else "no metrics"
        reach = fmt_num(e["perf"]["reach"], 2) if e["perf"] else "n/a"
        approx = "~" if e["approx"] else ""
        print(f"  {e['idea_slug']:<36} last {approx}{run['posted_at'][:10]}"
              f" ({e['days_since']}d ago, {e['run_count']} run{'s' if e['run_count'] != 1 else ''})"
              f" · eff {eff} · reach {reach}"
              f" · last: V{run['variant_id']} {run['v_format'] or '?'}/{run['v_hook'] or '?'}")

    print(f"\nNEVER RUN ({len(q['never'])})")
    if not q["never"]:
        print("  library is empty for this platform; ./crm import <dir> to load the swipe file")
    for idea in q["never"][:15]:
        marker = "" if idea["platform_variants"] else f"  [no {platform} variant yet]"
        print(f"  {idea['slug']:<36} {idea['title'][:52]}{marker}")
    if len(q["never"]) > 15:
        print(f"  ... and {len(q['never']) - 15} more (./crm ideas)")

    if q["cooling"]:
        nxt = q["cooling"][0]
        line = (f"\nIN COOLDOWN ({len(q['cooling'])}) · next eligible"
                f" {nxt['eligible_on']} ({nxt['idea_slug']})")
        print(line if args.all else line + " · --all to list")
        if args.all:
            for e in q["cooling"]:
                print(f"  {e['idea_slug']:<36} last {e['run']['posted_at'][:10]}"
                      f" ({e['days_since']}d ago) · eligible {e['eligible_on']}")


def cmd_status(conn, cfg, args):
    report = open_checkpoints(conn, cfg)
    print(f"OPEN CHECKPOINTS · runs from the last {cfg['status_window_days']}d\n")
    if not report:
        print("No runs in the window. Record one with: ./crm ran <variant>")
        return
    for item in report:
        run = item["run"]
        days = item["elapsed_hours"] / 24
        print(f"R{run['id']} {run['idea_slug']} V{run['variant_id']}"
              f" · posted {_when_label(run)} · {days:.1f}d ago")
        cells = []
        for cp in item["checkpoints"]:
            if cp["state"] == "done":
                cells.append(f"{cp['name']} done")
            elif cp["state"] == "due":
                cells.append(f"{cp['name']} DUE")
            elif cp["state"] == "missed":
                cells.append(f"{cp['name']} missed")
            else:
                remaining = (cp["hours"] - item["elapsed_hours"]) / 24
                cells.append(f"{cp['name']} in {remaining:.1f}d")
        if item["adhoc_count"]:
            cells.append(f"+{item['adhoc_count']} ad hoc")
        if item["no_metrics"]:
            cells.append("no data at all: worth an ad hoc snapshot")
        print("    " + " · ".join(cells))
    if any(i["anything_due"] for i in report):
        print("\nLog with: ./crm log [run] -i <impressions> -r <reactions> -c <comments>")


def cmd_ran(conn, cfg, args):
    variant = resolve_variant(conn, args.variant)
    posted_at, precision = parse_when(args.at)
    platform = variant["platform"]
    dow = dow_bucket(posted_at, precision)
    slot = slot_bucket(posted_at, precision, cfg["slots"])

    prev = latest_run_of_variant(conn, variant["id"])
    idea = resolve_idea(conn, str(variant["idea_id"]))
    idea_last = conn.execute(
        """SELECT r.posted_at FROM runs r JOIN variants v ON v.id = r.variant_id
           WHERE v.idea_id = ? AND r.platform = ? ORDER BY r.posted_at DESC LIMIT 1""",
        (variant["idea_id"], platform),
    ).fetchone()

    cur = conn.execute(
        "INSERT INTO runs (variant_id, platform, posted_at, posted_at_precision,"
        " dow_bucket, slot_bucket, followers_at_post, post_url, post_urn,"
        " created_at, notes)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (variant["id"], platform, posted_at, precision, dow, slot,
         args.followers, args.url, getattr(args, "urn", None) or None,
         now_iso(), args.note or ""),
    )
    conn.commit()
    run_id = cur.lastrowid

    slot_label = f"{dow} {slot}" if slot else (dow or "date approximate")
    print(f"Logged run R{run_id}: V{variant['id']} ({idea['slug']}) on {platform}")
    print(f"  posted {posted_at} ({slot_label})"
          + (f" · followers {args.followers}" if args.followers else ""))
    if args.followers is None:
        print("  warning: no --followers, so normalised reach will be unavailable for this run")
    if precision != "minute":
        print("  warning: no posting time, so slot comparisons with this run will be inconclusive")
    if variant["body"] is None:
        print("  warning: this variant has no body on record")
    if getattr(args, "urn", None):
        print(f"  urn {args.urn} recorded, so post analytics can read this run")
    else:
        print("  note: no --urn, so the analytics API cannot ever read this run")
    if prev is not None:
        since = int(elapsed_hours(prev["posted_at"]) / 24)
        print(f"  retest: V{variant['id']} last ran R{prev['id']} on"
              f" {prev['posted_at'][:10]} ({since}d ago)")
    elif idea_last is not None:
        since = int(elapsed_hours(idea_last["posted_at"]) / 24)
        cd = cfg["cooldown_days"].get(platform)
        print(f"  idea last ran {since}d ago on {platform} (cooldown {cd}d)")
    first_cp = min(cfg["checkpoints"].items(), key=lambda kv: kv[1])
    print(f"  next: ./crm log -i <impressions> at the {first_cp[0]} checkpoint")


def cmd_log(conn, cfg, args):
    run = resolve_run(conn, args.run)
    values = {f: getattr(args, f) for f in METRIC_FLAGS}
    if all(v is None for v in values.values()):
        hints = entry_hints(run["platform"])
        pairs = " · ".join(f"{k}: {v}" for k, v in hints.items())
        raise ValueError(
            f"no metrics given. On {run['platform']} enter: {pairs}")

    captured_at, _ = parse_when(args.at)
    if args.checkpoint:
        checkpoint = None if args.checkpoint == "adhoc" else args.checkpoint
        if checkpoint and checkpoint not in cfg["checkpoints"]:
            known = ", ".join(cfg["checkpoints"])
            raise ValueError(f"unknown checkpoint '{checkpoint}' (known: {known}, adhoc)")
    else:
        checkpoint = auto_checkpoint(cfg, elapsed_hours(run["posted_at"]))

    dup = checkpoint and conn.execute(
        "SELECT 1 FROM metrics WHERE run_id = ? AND checkpoint = ?",
        (run["id"], checkpoint),
    ).fetchone()

    conn.execute(
        "INSERT INTO metrics (run_id, checkpoint, captured_at, impressions, reactions,"
        " comments, reposts, saves, link_clicks, profile_visits, bookings, notes)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run["id"], checkpoint, captured_at, values["impressions"],
         values["reactions"], values["comments"], values["reposts"], values["saves"],
         values["link_clicks"], values["profile_visits"], values["bookings"],
         args.note or ""),
    )
    conn.commit()

    ctx = run_context(conn, run)
    perf = run_performance(conn, run, cfg)
    label = checkpoint or "ad hoc"
    print(f"Logged {label} metrics for {ctx['label']} ({ctx['idea_slug']} V{ctx['variant_id']})")
    entered = " · ".join(f"{k} {v}" for k, v in values.items() if v is not None)
    print(f"  {entered}")
    print(f"  score {fmt_num(perf['score'], 2)} · eff {fmt_num(perf['efficiency'])}"
          f" · reach {fmt_num(perf['reach'], 2)}")
    if dup:
        print(f"  note: second {checkpoint} snapshot for this run; the latest capture wins for scoring")


# ---------------------------------------------------------------- library

def cmd_ideas(conn, cfg, args):
    sql = """
      SELECT i.*, COUNT(DISTINCT v.id) AS n_variants, COUNT(DISTINCT r.id) AS n_runs,
             MAX(r.posted_at) AS last_posted
      FROM ideas i
      LEFT JOIN variants v ON v.idea_id = i.id
      LEFT JOIN runs r ON r.variant_id = v.id
    """
    params = []
    if args.search:
        sql += " WHERE i.slug LIKE ? OR i.title LIKE ? OR i.thesis LIKE ? OR i.tags LIKE ?"
        params = [f"%{args.search}%"] * 4
    sql += " GROUP BY i.id ORDER BY i.created_at DESC, i.id DESC"
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        print("no ideas" + (f" matching '{args.search}'" if args.search else " yet"))
        return
    print(f"{'id':<5} {'slug':<36} {'var':>3} {'runs':>4} {'last posted':<12} title")
    for r in rows:
        last = (r["last_posted"] or "never")[:10]
        status = "" if r["status"] == "active" else f" [{r['status']}]"
        print(f"I{r['id']:<4} {r['slug']:<36} {r['n_variants']:>3} {r['n_runs']:>4}"
              f" {last:<12} {r['title'][:48]}{status}")


def _print_variant_line(conn, cfg, variant, indent):
    legacy = f" ({variant['legacy_post_id']})" if variant["legacy_post_id"] else ""
    attrs = "/".join(x for x in (variant["format"], variant["hook_archetype"]) if x) or "?"
    wc = f" · {variant['word_count']}w" if variant["word_count"] else ""
    body_note = "" if variant["body"] else " · body not recorded"
    print(f"{indent}V{variant['id']}{legacy} {variant['platform']} {attrs}{wc}{body_note}")
    runs = conn.execute(
        "SELECT * FROM runs WHERE variant_id = ? ORDER BY posted_at, id",
        (variant["id"],),
    ).fetchall()
    for run in runs:
        perf = run_performance(conn, run, cfg)
        cells = " · ".join(c for c in _perf_cells(perf) if c)
        print(f"{indent}   R{run['id']} {_when_label(run)} · {cells}")


def _print_variant_tree(conn, cfg, idea_id):
    variants = conn.execute(
        "SELECT * FROM variants WHERE idea_id = ? ORDER BY id", (idea_id,)
    ).fetchall()
    by_parent = {}
    ids = {v["id"] for v in variants}
    for v in variants:
        parent = v["derived_from_variant_id"]
        key = parent if parent in ids else None
        by_parent.setdefault(key, []).append(v)

    def walk(parent_key, depth):
        for v in by_parent.get(parent_key, []):
            _print_variant_line(conn, cfg, v, "   " + "      " * depth)
            walk(v["id"], depth + 1)

    walk(None, 0)


def cmd_show(conn, cfg, args):
    ref = args.ref.strip()
    kind, row = None, None
    try:
        if ref[:1] in "Rr" and ref[1:].isdigit():
            kind, row = "run", resolve_run(conn, ref)
        elif ref[:1] in "Vv" and ref[1:].isdigit():
            kind, row = "variant", resolve_variant(conn, ref)
        elif ref[:1] in "Ii" and ref[1:].isdigit():
            kind, row = "idea", resolve_idea(conn, ref)
        elif ref.startswith("post-"):
            kind, row = "variant", resolve_variant(conn, ref)
        else:
            kind, row = "idea", resolve_idea(conn, ref)
    except RefError:
        if kind is None or kind == "idea":
            try:
                kind, row = "variant", resolve_variant(conn, ref)
            except RefError:
                raise RefError(f"nothing matches '{ref}' (idea slug, I#, V#, R#, post-NNN)")
        else:
            raise

    if kind == "idea":
        print(f"I{row['id']} {row['slug']} · {row['title']}")
        print(f"   source {row['source']} · created {row['created_at'][:10]}"
              f" · status {row['status']} · tags {row['tags']}")
        if row["thesis"]:
            print(f"   thesis: {row['thesis']}")
        if row["notes"]:
            print(f"   notes: {row['notes']}")
        print()
        _print_variant_tree(conn, cfg, row["id"])

    elif kind == "variant":
        if args.body:
            if row["body"] is None:
                raise ValueError(f"V{row['id']} has no body on record")
            print(row["body"])
            return
        idea = resolve_idea(conn, str(row["idea_id"]))
        print(f"V{row['id']}"
              + (f" ({row['legacy_post_id']})" if row["legacy_post_id"] else "")
              + f" · idea {idea['slug']} (I{idea['id']}) · {row['platform']}")
        attrs = [("format", row["format"]), ("hook", row["hook_archetype"]),
                 ("cta", row["cta_type"]), ("media", row["media_type"]),
                 ("stage", row["stage"]), ("words", row["word_count"])]
        print("   " + " · ".join(f"{k} {v}" for k, v in attrs if v is not None))
        if row["derived_from_variant_id"]:
            print(f"   rewrite of V{row['derived_from_variant_id']}"
                  f" (compare with: ./crm compare V{row['id']})")
        children = conn.execute(
            "SELECT id FROM variants WHERE derived_from_variant_id = ?", (row["id"],)
        ).fetchall()
        if children:
            print("   rewrites: " + ", ".join(f"V{c['id']}" for c in children))
        if row["notes"]:
            print(f"   notes: {row['notes']}")
        if row["body"]:
            preview = row["body"].strip().splitlines()
            print("\n   " + "\n   ".join(preview[:3]))
            if len(preview) > 3:
                print(f"   ... ({len(preview) - 3} more lines; --body for all of it)")
        else:
            print("\n   body not recorded")
        print()
        runs = conn.execute(
            "SELECT * FROM runs WHERE variant_id = ? ORDER BY posted_at, id", (row["id"],)
        ).fetchall()
        if not runs:
            print("   never run")
        for run in runs:
            perf = run_performance(conn, run, cfg)
            cells = " · ".join(c for c in _perf_cells(perf) if c)
            print(f"   R{run['id']} {_when_label(run)} · {cells}")

    else:  # run
        ctx = run_context(conn, row)
        print(f"{ctx['label']} · {ctx['idea_slug']} V{ctx['variant_id']} · {row['platform']}")
        print(f"   posted {_when_label(row)}"
              + (f" · followers {row['followers_at_post']}" if row["followers_at_post"] else " · followers not recorded"))
        if row["post_url"]:
            print(f"   url {row['post_url']}")
        if row["notes"]:
            print(f"   notes: {row['notes']}")
        snaps = conn.execute(
            "SELECT * FROM metrics WHERE run_id = ? ORDER BY captured_at, id", (row["id"],)
        ).fetchall()
        if not snaps:
            print("   no metrics yet")
            return
        print(f"\n   {'checkpoint':<11} {'captured':<17} {'imp':>6} {'rxn':>4} {'com':>4}"
              f" {'rep':>4} {'sav':>4} {'clk':>4} {'vis':>4} {'book':>4}")
        for m in snaps:
            cells = [m[k] for k in METRIC_FLAGS]
            cells = [str(c) if c is not None else "." for c in cells]
            print(f"   {m['checkpoint'] or 'ad hoc':<11} {m['captured_at']:<17}"
                  f" {cells[0]:>6} {cells[1]:>4} {cells[2]:>4} {cells[3]:>4}"
                  f" {cells[4]:>4} {cells[5]:>4} {cells[6]:>4} {cells[7]:>4}")
        perf = run_performance(conn, row, cfg)
        print(f"\n   score {fmt_num(perf['score'], 2)} · eff {fmt_num(perf['efficiency'])}"
              f" · reach {fmt_num(perf['reach'], 2)} (latest snapshot)")


def cmd_idea(conn, cfg, args):
    slug = unique_slug(conn, slugify(args.title))
    tags = json.dumps([t.strip() for t in (args.tags or "").split(",") if t.strip()])
    cur = conn.execute(
        "INSERT INTO ideas (slug, title, thesis, tags, created_at) VALUES (?, ?, ?, ?, ?)",
        (slug, args.title, args.thesis, tags, now_iso()),
    )
    conn.commit()
    print(f"I{cur.lastrowid} {slug} created. Add the writing: ./crm draft {slug} --body-file <f>")


def _insert_variant(conn, idea_id, platform, body, args, derived_from=None,
                    inherit=None, note=""):
    def attr(name):
        explicit = getattr(args, name, None)
        if explicit is not None:
            return explicit
        return inherit[name] if inherit is not None else None

    cur = conn.execute(
        "INSERT INTO variants (idea_id, platform, derived_from_variant_id, body,"
        " hook_archetype, format, cta_type, media_type, stage, word_count, created_at, notes)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (idea_id, platform, derived_from, body, attr("hook_archetype"), attr("format"),
         attr("cta_type"), attr("media_type"), attr("stage"), len(body.split()),
         now_iso(), note),
    )
    conn.commit()
    return cur.lastrowid


def cmd_draft(conn, cfg, args):
    idea = resolve_idea(conn, args.idea)
    body = _read_body(args)
    platform = normalise(args.platform or cfg["default_platform"])
    vid = _insert_variant(conn, idea["id"], platform, body, args)
    print(f"V{vid} added to {idea['slug']} ({platform}, {len(body.split())}w)")
    print(f"  after you publish it: ./crm ran V{vid} --followers <n>")


def cmd_rewrite(conn, cfg, args):
    parent = resolve_variant(conn, args.variant)
    body = _read_body(args)
    vid = _insert_variant(
        conn, parent["idea_id"], parent["platform"], body, args,
        derived_from=parent["id"], inherit=parent,
        note=f"rewrite of V{parent['id']}",
    )
    print(f"V{vid} created as a rewrite of V{parent['id']} (same idea, {len(body.split())}w)")
    print(f"  after both have comparable runs: ./crm compare V{vid}")


def cmd_compare(conn, cfg, args):
    if args.b:
        run_a = resolve_run(conn, args.a)
        run_b = resolve_run(conn, args.b)
        if run_a["id"] == run_b["id"]:
            raise ValueError("both references point at the same run")
    else:
        child = resolve_variant(conn, args.a)
        if not child["derived_from_variant_id"]:
            raise ValueError(
                f"V{child['id']} has no parent; give two references: ./crm compare A B")
        parent = resolve_variant(conn, str(child["derived_from_variant_id"]))
        run_a = latest_run_of_variant(conn, child["id"])
        run_b = latest_run_of_variant(conn, parent["id"])
        if run_a is None or run_b is None:
            missing = f"V{child['id']}" if run_a is None else f"V{parent['id']}"
            raise ValueError(f"{missing} has never run; nothing to compare yet")

    result = compare_runs(conn, cfg, run_a, run_b, metric=args.metric)
    a, b = result["a"], result["b"]
    print(f"COMPARE {a['label']} vs {b['label']} · metric: {result['metric']}")
    for ctx in (a, b):
        run = ctx["run"]
        print(f"  {ctx['label']}: {ctx['idea_slug']} V{ctx['variant_id']}"
              f" ({ctx['format'] or '?'}/{ctx['hook'] or '?'}) · posted {_when_label(run)}")
    print()
    for g in result["gates"]:
        print(f"  [{'ok' if g['ok'] else 'X '}] {g['detail']}")
    if result.get("snapshot_note"):
        print(f"  snapshots: {result['snapshot_note']}")
    if result.get("snapshot_warning"):
        print(f"  warning: {result['snapshot_warning']}")
    print()

    if result["verdict"] == "INCONCLUSIVE":
        print("VERDICT: INCONCLUSIVE. These runs cannot honestly be compared.")
        for reason in result["reasons"]:
            print(f"  {reason}")
        return
    va, vb = result["values"]["a"], result["values"]["b"]
    print(f"  {a['label']}: {result['metric']} {fmt_num(va, 4)}")
    print(f"  {b['label']}: {result['metric']} {fmt_num(vb, 4)}")
    if result["verdict"] == "NOISE":
        print(f"\nVERDICT: NOISE. Gap is {result['gap_pct']:.0f}%, below the"
              f" {cfg['min_effect_pct']}% threshold. Do not act on this.")
        return
    winner, loser = (a, b) if result["winner"] == "a" else (b, a)
    if result.get("zero_loser"):
        print(f"\nVERDICT: {winner['label']} wins; {loser['label']} scored zero,"
              " so the margin is undefined.")
    else:
        print(f"\nVERDICT: {winner['label']} beats {loser['label']} by"
              f" {result['gap_pct']:.0f}% on {result['metric']}.")
    print(f"  {CAVEAT}")


# ---------------------------------------------------------------- setup

def cmd_init(conn, cfg, args):
    created = write_default_config()
    print(f"config: {CONFIG_PATH}" + ("" if created else " (already existed, untouched)"))
    print(f"db:     {db_path(cfg)}")
    counts = {t: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
              for t in ("ideas", "variants", "runs", "metrics")}
    print("tables: " + " · ".join(f"{k} {v}" for k, v in counts.items()))
    if counts["ideas"] == 0:
        print("next:   ./crm migrate   (one-time posts.jsonl import)")


def cmd_migrate(conn, cfg, args):
    path = args.jsonl or (ROOT / "posts.jsonl")
    summary = migrate_posts_jsonl(conn, path, cfg)
    print(f"Migrated {path}:")
    print(f"  {summary['ideas']} ideas · {summary['variants']} variants"
          f" · {summary['runs']} runs · {summary['metrics']} metric snapshots")
    if summary["siblings"]:
        sib = summary["siblings"]
        idea_ids = {s["idea_id"] for s in sib}
        pairs = ", ".join(f"{s['legacy_id']} -> V{s['variant_id']}" for s in sib)
        ok = "one shared idea, correct" if len(idea_ids) == 1 else "ERROR: not one idea!"
        print(f"  siblings: {pairs} under I{sib[0]['idea_id']}"
              f" '{sib[0]['idea_slug']}' ({ok})")
    print("  followers_at_post is unknown for legacy runs, so their normalised"
          " reach stays n/a; efficiency still works.")


def cmd_import(conn, cfg, args):
    platform = normalise(args.platform or cfg["default_platform"])
    summary = import_markdown_dir(conn, args.dir, platform, cfg)
    for slug_pair in summary["created"]:
        print(f"  new     {slug_pair[0]} -> {slug_pair[1]}")
    for rel in summary["updated"]:
        print(f"  updated {rel} (unposted draft, body replaced)")
    for rel in summary["rewritten"]:
        print(f"  rewrite {rel} (already ran; created a child variant)")
    for rel in summary["skipped_empty"]:
        print(f"  skipped {rel} (no body)")
    n_unchanged = len(summary["skipped_unchanged"])
    if n_unchanged:
        print(f"  unchanged: {n_unchanged} file{'s' if n_unchanged != 1 else ''}")
    total = sum(len(v) for v in summary.values())
    if total == 0:
        print(f"  no .md files under {args.dir}")


# ---------------------------------------------------------------- parser

def build_parser():
    ap = argparse.ArgumentParser(
        prog="crm",
        description="Content library, lineage and recycling. You publish by hand;"
                    " this remembers what ran, how it did, and what is due for a retest.",
    )
    ap.add_argument("--db", help="override database path (default: config db_path)")
    ap.add_argument("--config", help="override config file path (default: ./config.json)")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="command")

    p = sub.add_parser("due", help="what to post: past-cooldown ideas ranked, plus never-run")
    p.add_argument("-p", "--platform")
    p.add_argument("--all", action="store_true", help="also list ideas still in cooldown")
    p.set_defaults(func=cmd_due)

    p = sub.add_parser("status", help="which recent runs need 24h/72h/7d metrics")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("ran", help="record that you published a variant (the tool never posts)")
    p.add_argument("variant", help="V12, bare id, or legacy post-NNN")
    p.add_argument("--at", help="'YYYY-MM-DD HH:MM' (default: now)")
    p.add_argument("--followers", type=int, help="your follower count right now")
    p.add_argument("--url", help="link to the live post")
    p.add_argument("--urn", help="urn:li:share:... if you have it; required for API analytics")
    p.add_argument("--note")
    p.set_defaults(func=cmd_ran)

    p = sub.add_parser("log", help="add a metrics snapshot to a run (default: latest run)")
    p.add_argument("run", nargs="?", help="R7, V12, post-NNN, or blank for the latest run")
    p.add_argument("-i", "--impressions", type=int)
    p.add_argument("-r", "--reactions", type=int)
    p.add_argument("-c", "--comments", type=int)
    p.add_argument("--reposts", type=int)
    p.add_argument("--saves", type=int)
    p.add_argument("--clicks", dest="link_clicks", type=int)
    p.add_argument("--visits", dest="profile_visits", type=int)
    p.add_argument("--bookings", type=int)
    p.add_argument("--cp", dest="checkpoint", help="24h | 72h | 7d | adhoc (default: auto from elapsed time)")
    p.add_argument("--at", help="when these numbers were read (default: now)")
    p.add_argument("--note")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("ideas", help="list the library")
    p.add_argument("--search", help="substring across slug/title/thesis/tags")
    p.set_defaults(func=cmd_ideas)

    p = sub.add_parser("show", help="idea, variant, or run in detail")
    p.add_argument("ref", help="idea slug, I3, V12, R7, or post-NNN")
    p.add_argument("--body", action="store_true",
                   help="print only the variant body (pipe it to pbcopy)")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("idea", help="add an idea by hand")
    p.add_argument("title")
    p.add_argument("--thesis")
    p.add_argument("--tags", help="comma separated")
    p.set_defaults(func=cmd_idea)

    for name, help_text in (("draft", "add a variant to an idea"),
                            ("rewrite", "add a child variant derived from an existing one")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("idea" if name == "draft" else "variant")
        p.add_argument("--body")
        p.add_argument("--body-file", help="path, or '-' for stdin")
        if name == "draft":
            p.add_argument("--platform")
        p.add_argument("--hook", dest="hook_archetype")
        p.add_argument("--format", dest="format")
        p.add_argument("--cta", dest="cta_type")
        p.add_argument("--media", dest="media_type")
        p.add_argument("--stage", type=int, choices=[1, 2, 3, 4])
        p.set_defaults(func=cmd_draft if name == "draft" else cmd_rewrite)

    p = sub.add_parser("compare", help="verdict between two runs, or a variant vs its parent")
    p.add_argument("a", help="V12, R7, post-NNN; alone = this variant vs its parent")
    p.add_argument("b", nargs="?")
    p.add_argument("--metric", choices=["efficiency", "reach"],
                   help="decision metric (default from config)")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("init", help="create content.db and config.json")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("migrate", help="one-time import of the legacy posts.jsonl")
    p.add_argument("jsonl", nargs="?", help="path (default: ./posts.jsonl)")
    p.set_defaults(func=cmd_migrate)

    p = sub.add_parser("import", help="import a directory of markdown into the library")
    p.add_argument("dir")
    p.add_argument("-p", "--platform", help="platform for the imported variants (default from config)")
    p.set_defaults(func=cmd_import)

    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    if args.db:
        cfg["db_path"] = args.db
    conn = connect(db_path(cfg))
    try:
        args.func(conn, cfg, args)
        return 0
    except (RefError, ValueError) as e:
        print(f"crm: {e}", file=sys.stderr)
        return 2
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
