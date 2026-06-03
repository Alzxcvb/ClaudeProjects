# Erasure — "all-encompassing" build (thread-driven)

Source playbook: hrswatigupta_official Threads thread (9-step manual digital-footprint wipe).
Goal: cover the whole thread in the engine; keep every output JSON/web-consumable so a
front-facing website can wrap the CLI later.

## Plan

- [ ] **Phase 1 — `legal/` deletion-letter generator** (thread Step 4)
  - `erasure/legal/templates.py` — CCPA / GDPR / generic deletion-request bodies, citing the law.
  - `erasure/legal/generator.py` — `render_request(profile, jurisdiction, recipient, ...)`.
  - CLI: `erasure legal request --jurisdiction ccpa|gdpr|generic [--recipient ...]`, `erasure legal list`.
  - Tests: render each jurisdiction, profile substitution, law citation present, no em-dashes.

- [ ] **Phase 2 — `tracker` ledger** (thread Step 2)
  - `erasure/tracker.py` — rows: site, opt_out_url, method, date_requested, status, follow_up_date.
  - Seed from broker registry + scan manifest; update status; CSV/JSON export.
  - CLI: `erasure tracker init|add|update|show|export`.
  - Tests.

- [ ] **Phase 3 — justdelete.me bridge** (thread Steps 5 + 6)
  - `erasure/accounts/justdelete.py` — bundled curated directory (name, domain, difficulty, delete URL/notes).
  - Cross-ref latest accounts/emails manifest → deletion difficulty + direct link; flag scrub-first for hard/impossible.
  - CLI: `erasure accounts deletion-links`.
  - Tests.

- [ ] **Phase 4 — `playbook` + wire `schedule`** (thread Steps 1,7,8,9)
  - `erasure/playbook.py` — full 9-step playbook with the exact command for each step.
  - CLI: `erasure playbook`.
  - Wire stubbed `schedule` → emit a real quarterly re-check reminder (crontab/launchd line).
  - Tests.

- [ ] **Phase 5 — docs / web roadmap / memory**
  - README new commands; `ROADMAP-web.md` (thin web layer over engine); update project-erasure memory; portfolio if needed.

## Conventions to honor
- Stage by explicit path; inspect `git diff --cached` before commit (shared parent repo).
- Commit + push after each phase.
- No em dashes in any user-facing copy (legal letters included) — AI tell.
- Keep tests green (baseline 97/97).

## Review
(filled in as phases complete)
