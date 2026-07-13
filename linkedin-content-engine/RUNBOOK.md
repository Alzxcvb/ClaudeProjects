# LinkedIn Content Engine — Runbook

Quick reference for daily operation. See [`PLAN.md`](PLAN.md) for the why, [`README.md`](README.md) for setup.

---

## Daily routine (5 minutes)

### Morning (post)
1. Notification fires at 9:00 local (after `install-reminders.sh`).
2. Ask the queue what's worth posting:
   ```bash
   cd /Users/alexandercoffman/Dev/linkedin-content-engine
   ./crm due
   ```
   Top section = ideas past their 90-day cooldown, ranked by how they did last time. Below it = the never-run backlog.
3. Grab the text and post it yourself (**Cmd+Shift+V** for plain-text paste):
   ```bash
   ./crm show V12 --body | pbcopy
   ```
4. Record the publication, with your current follower count off your profile:
   ```bash
   ./crm ran V12 --followers 520 --url https://www.linkedin.com/posts/...
   ```
   Skipping `--followers` kills normalised reach for that run. It's one number, grab it.

### Evening (log)
1. Notification fires at 18:00 local (Tue-Fri).
2. See what's due:
   ```bash
   ./crm status
   ```
3. Pull the numbers off the post's "View analytics" and log them (defaults to the latest run; the 24h/72h/7d label is picked from elapsed time):
   ```bash
   ./crm log -i 210 -r 5 -c 2
   ```
   Extra signals when you have them: `--reposts --saves --clicks --visits --bookings`.

That's it.

---

## Weekly-ish

- `./crm compare V18` — after a rewrite has a comparable run, ask if it beat its parent. The answer is a verdict, NOISE, or an honest INCONCLUSIVE with the reason. Clean tests need same day-of-week + same slot, one week apart (PLAN.md §4).
- `./crm import <dir>` — re-run whenever the markdown swipe file grows or changes. Idempotent; edited files that already ran become child variants automatically.
- `./crm ideas --search <q>` / `./crm show <slug>` — browse the library and lineage.

---

## What's where

| File | Purpose |
|---|---|
| `content.db` | SQLite source of truth: ideas / variants / runs / metrics. **Gitignored.** |
| `crm` | The CLI. `./crm <command> -h` for flags. |
| `config.json` | Score weights, cooldowns per platform, time slots, checkpoints, 40% noise threshold. Edit freely. |
| `contentcrm/` | Implementation (schema.sql, migration, markdown import, queue, compare). |
| `generate.py` | LLM call: topic → 3 variants. Few-shot = last 10 runs **with bodies** from the db. |
| `predict.py` | LLM call: variant → forecast. History = all labeled runs from the db. |
| `prompts/generator.md` | Voice rules + ban list. Edit to tune voice. |
| `prompts/predictor.md` | Calibration rules. Edit to tune forecasts. |
| `posts.jsonl` | Legacy archive (migrated 2026-07-10). Nothing reads it. |
| `log.py` | Legacy; warns and points at `./crm log`. |
| `scripts/install-reminders.sh` | One-time cron reminders. |
| `tests/` | `.venv/bin/python -m unittest discover` |

Platforms: the schema is platform agnostic. `./crm due -p x`, `./crm draft <idea> --platform instagram`, same manual metric entry everywhere. Cooldowns: LinkedIn 90d, X 30d, Instagram 120d (config).

---

## Install the daily reminders

One-time setup:

```bash
bash /Users/alexandercoffman/Dev/linkedin-content-engine/scripts/install-reminders.sh
```

This adds two crontab entries:
- Mon-Thu 9:00 local — notification: "time to post"
- Tue-Fri 18:00 local — notification: "log yesterday's metrics"

**First-run gotcha:** macOS may need to grant notification permission to whatever process is running cron (often System Events). If you don't see the test notification at the end of the install script, open System Settings > Notifications and ensure `cron` / `System Events` are allowed to post notifications.

To remove later: `crontab -e` and delete the lines under `# linkedin-content-engine reminders`.

---

## Funnel-stage discipline

Every variant has a `stage` field (1-4). Hard rules:

| Stage | Allowed | Forbidden |
|---|---|---|
| 1 Problem Unaware | Pain framing, observation, contrarian take | ANY price mention, ANY service mention, any CTA beyond a question |
| 2 Problem Aware | Sharpen the pain from READER's perspective | Service mention, price mention |
| 3 Solution Aware | Generic service description ("a 90-min setup") | Hard CTAs ("DM me", "book now"), fake scarcity |
| 4 Product Aware | Pitching is the point — name service, name price, soft CTA | Fabricated testimonials, fake scarcity |

Failure mode caught 2026-06-02: post-006 had a Stage-1 topic but included a $200 service price line. Underperformed at half post-005's reach in the same 24h. See [feedback_funnel_stage_discipline](../../../.claude/projects/-Users-alexandercoffman-ClaudeProjects/memory/feedback_funnel_stage_discipline.md).

---

## Honest signals from the first 7 posts (n=7, 2026-06-03)

1. **Short-punchy > long-form, confirmed.** post-001 (130w, 202 imp) > post-002 (280w, 120 imp) at same age. Ratio: 1.68×. Both grew over the week; long grew faster (+52% vs +23%) so the gap is narrowing. (Note from the migration: on **efficiency** post-002 actually edges post-001, 0.060 vs 0.055 — a 10% gap, i.e. noise. The impressions "win" and the efficiency read disagree, which is exactly why the tool refuses to compare runs whose time slots are unknown.)
2. **One clean number > multi-number framing.** post-005 (one anchor: "4 hours") = 261 imp vs post-004 (two anchors: "$40/hr → $10k, $150/hr → $37,500") = 77 imp. The multi-rate math forced the reader to do work.
3. **Stage-1 pitch hurts reach, visibly.** post-006 (pitched in Stage 1) = 99 imp vs post-007 (clean Stage 2) = 164 imp, same day. Pitch leaked, audience disengaged.
4. **Contrarian reframe pulls comments.** post-007's "permission-to-stop, not productivity" reframe got 5 substantive comments. None of the commenters are real ICP — they're networking-comment LinkedIn pros (LinkedIn coaches, ghostwriters, B2B GTM). Engagement ≠ conversion.
5. **The repeat-commenter pattern is real.** Neha Malhotra and Krati Agarwal commented on multiple posts. Both are LinkedIn networking-bots, not target customers. Worth tracking who actually clicks through to the site / books a call — `--clicks` and `--bookings` on `./crm log` exist for exactly this, once the tracked link + Calendly question are set up.

---

## What's NOT built yet

- Click-through attribution — no `hiimalex.ai/p/NN` redirect, so `--clicks` has no data source yet.
- Booking attribution — Calendly doesn't ask "where did you find me?", so `--bookings` is manual knowledge.
- Metric scraping — chrome-mcp auto-capture of the 3 checkpoints (PLAN.md Phase 2). Manual entry until then.
- Reply drafting for comments on Alex's own posts (approve via JARVIS Telegram) — PLAN.md Phase 3.
- Commenter CRM — `comment_authors` is preserved on runs but there's no relationship layer yet.
