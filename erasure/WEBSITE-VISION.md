# Erasure: front-facing website vision

The goal: a hosted site that asks for your information, then walks you through
deleting your footprint. Where a site is hostile to automation (anti-bot,
CAPTCHA, terms that forbid it, or it needs your logged-in session), the same
flow falls back to a guided experience you run locally after downloading the
repo. This doc maps what is already built (the CLI engine) onto that vision and
lays out the phases.

## The core split: hosted vs. local

The dividing line is **whose session and machine the action needs**.

**Hosted (runs on our server, no user secrets required):**
| Capability | CLI today | Web-readiness |
|---|---|---|
| Profile intake | `erasure init` | Trivial form. Stays in the browser / encrypted at rest. |
| The 9-step checklist | `erasure playbook` | Pure render. Ship as the landing experience. |
| Legal deletion letters | `erasure legal request` | Pure function of the profile. Generate + offer `mailto:` / copy. |
| Tracking ledger + CSV | `erasure tracker` | Pure data. Per-user ledger, exportable. |
| Broker scan (read-only) | `erasure scan` | Server-side Playwright, but expect bot-detection and cost at scale. Queue + rate-limit. |
| DROP request prep | `erasure drop ...` | Collect + pre-fill, but the identity OTP must be completed by the user. |

**Local (must run on the user's machine, with their session):**
| Capability | Why it can't be hosted | CLI today |
|---|---|---|
| Deleting dead accounts | Needs the user's authenticated session per service; we must never hold their passwords | `erasure accounts deletion-links` surfaces the targets + direct links |
| Sites with CAPTCHA / anti-bot / no-automation ToS | Server automation gets blocked or violates terms | per-broker `opt-out` (stub) |
| Scrub-before-delete | Inherently interactive (junk name, alias email, blank profile) | flagged by `--scrub-only` |
| Finishing a DROP OTP | The code goes to the user's phone | `drop submit` stops at "Send code" today |

This is exactly the user's framing: the website handles the privacy-friendly,
automatable surface; the "not privacy-friendly" surface becomes a guided UX the
user runs locally after downloading from GitHub, so their credentials and
session never leave their device.

## Why this is the right architecture (not just a constraint)

A privacy product must not become a new data broker. Keeping account-deletion
and anything credential-bearing on the user's own machine is the feature, not a
limitation: the hosted side only ever sees the identifiers the user would put on
a public opt-out form anyway, and the sensitive work runs where the data already
lives.

## Phased plan

**Phase A: static playbook site (fastest, no backend). [SHIPPED 2026-06-04]**
Lives at `erasure/web/index.html` as a single self-contained file. Renders the
9-step playbook as an interactive checklist, generates CCPA/GDPR/generic legal
letters off a local profile, and runs a client-side tracker with a 45-day
follow-up clock and CSV export. Everything runs in the browser; state is held in
localStorage and never leaves the device (with a "clear all my data" button).
The step text, legal templates, and tracker columns are ported faithfully from
the Python CLI (`playbook.py`, `legal/templates.py`, `tracker.py`); a node
harness verifies the ported logic matches. Open it directly (file://) or host it
on any static host (GitHub Pages / Vercel).

**Phase B: accounts + local runner handoff.**
Add the account-discovery results (Sherlock / holehe) and the justdelete.me
deletion directory as a web view, with a one-command local runner
(`pipx install erasure` or a packaged binary) for the steps that need the user's
session. The site generates a personalized run file; the local tool consumes it.

**Phase C: hosted scan + DROP assist (backend).**
Per-user accounts, queued server-side broker scans, DROP request pre-fill with
user-completed OTP, and verification re-scans on the 45-day clock. This is where
real infrastructure (auth, a job queue, Playwright workers, secret-free storage)
is required, and where the "managed verification" paid tier could live.

## Open questions to resolve before Phase C

- Hosting for Playwright at scale without tripping broker bot-detection (residential egress? per-user rate caps?).
- Storage model that keeps us out of data-broker territory (client-side-only vs. encrypted-at-rest with user-held keys).
- Legal review of running broker-opt-out automation as a service vs. as a tool the user runs themselves.
- Whether the local runner ships as the Python CLI, a packaged desktop app, or a browser extension that drives the user's own tabs.
