# Pomodoro + Calisthenics — PLAN

**Status:** Bare-bones plan (2026-05-19). Not built. Smallest of this batch — 1-2 day build.

## What this is
A Pomodoro timer that turns 5-minute breaks into prescribed calisthenics. By end of day = hundreds of push-ups; by end of week = thousands.

## Architecture (minimum viable form: CLI)

```
$ pomo start

[focus 25m]  ──→ notify start, notify 5-min-warning, notify end
[break  5m]  ──→ notify with prescribed exercise
                    pick from config:
                       push-ups: 20-40 reps
                       squats:   30-50 reps
                       plank:    45-90 sec
                       crunches: 30-60 reps
                       burpees:  10-20 reps
                    log:  date, time, exercise, reps, done|skipped
$ pomo done    ──→ marks exercise done
$ pomo skip    ──→ marks exercise skipped
$ pomo stats   ──→ today + week totals per exercise
```

Storage: `~/.pomo-calisthenics.db` (SQLite).
Notifications: `terminal-notifier` or `osascript`.

## Tech stack (proposed)
- Python (single file) — fastest path
- SQLite — built-in
- `terminal-notifier` — macOS notifications without extra runtime

No GUI in v1. Add Tauri menu bar only if CLI is painful.

## Build order
1. `exercises.yaml` config
2. `pomo` CLI: start / done / skip / stats
3. Wire `terminal-notifier`
4. Use it for one week, iterate on exercise mix
5. (Optional) Tauri menu bar app

## Dependencies on other projects
None.

## SaaS rejected
- Stretchly — break reminders but no exercise prescription
- Standard Pomodoro apps — ignore the body

Too small to justify a SaaS dependency.

## Open questions
- Should it pause when meetings are on calendar? (could pull from JARVIS's calendar tools — defer)
- Weighted random vs strict rotation across exercises? (start weighted random)
- Should it block keyboard during breaks to force the exercise? (no — too aggressive for v1)
