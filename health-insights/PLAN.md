# Health Insights Dashboard — PLAN

**Status:** Bare-bones plan (2026-05-19). Not built.

## What this is
Single dashboard aggregating Alex's health data from 5+ disconnected sources, with a weekly Claude pass for anomaly detection and lead-lag correlations.

## Why
The "weight drop precedes sickness by ~1 week" pattern from LA personal-trainer days is the proof point: cross-source aggregation surfaces patterns that single apps can't. None of Alex's current tools (Apple Health, Lose It, Screen Time, blood work PDFs) talk to each other.

## Sources

| Source | What it gives | How to ingest |
|---|---|---|
| Apple Health (HealthKit) | sleep, weight, HRV, RHR | Already → JARVIS via Auto Export |
| Apple Watch workouts | sessions, HR, calories | Already → JARVIS via Auto Export |
| Lose It | calories, protein | Already → JARVIS via Auto Export |
| JARVIS daily check-ins | mood, sleep quality, energy, daily note | **NEEDS JARVIS's planned check-in prompter to exist first** |
| Screen Time (iOS + macOS) | hours/day per app | Parse macOS `Knowledge.db` + iOS Shortcut weekly export. **TIME-SENSITIVE — Apple rolls deletes after 4 weeks.** |
| Blood work | labs | Manual entry (CLI) + optional PDF parser |
| DEXA scans | body comp | Manual entry |

## Architecture

```
Sources ────→ ingest jobs (cron) ────→ SQLite (./db/health.sqlite)
                                              │
                                              ├── raw tables per source
                                              ├── normalized daily_metrics view
                                              │
                                              ▼
                                   Weekly Claude pass
                                   - rolling-baseline anomalies
                                   - lead-lag correlations
                                              │
                                              ▼
                                   findings table
                                              │
                                              ▼
                                   Streamlit dashboard
```

## Tech stack (proposed)
- Python (matches world3-dashboard, easier scientific libs)
- SQLite (sufficient for personal scale; Postgres later if shared)
- Anthropic SDK for the analysis pass
- Streamlit for UI (Alex knows it from world3-dashboard)

## Build order
1. JARVIS check-in prompter must land first (only missing source)
2. Unified schema design (`daily_metrics` view)
3. JARVIS Postgres → SQLite mirror (easiest source — already structured)
4. Screen Time archive job (most time-sensitive — data rolling-deletes)
5. Manual entry CLI for blood work / DEXA
6. Weekly Claude anomaly + correlation pass
7. Streamlit UI

## Dependencies on other projects
- `jarvis/` — primary data source; specifically the planned daily check-in prompter

## SaaS rejected
- Bearable, Welltory, Levels — all single-source. None aggregate Alex's full stack AND let an LLM reason for lead-lag patterns.

## Open questions
- Where does this run? Local-only on Mac (private) or Railway (accessible from phone)?
- How aggressive should anomaly alerts be — surface via JARVIS push, or pull-only via dashboard?
- Privacy: blood work + body comp are sensitive. Local-only by default.
