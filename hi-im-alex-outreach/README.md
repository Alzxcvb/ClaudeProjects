# Hi I'm Alex — Outreach POC

**Status:** Proof-of-concept (2026-05-19). Does NOT send emails. Drafts everything for human review first.

## What this is

Cold-outreach pipeline targeting Reddit commenters with AI/automation pain signals. DIY stack, $0/month recurring (except optional Gmail Workspace later). Built to test whether the pattern produces qualified leads before investing in scaling.

**Designed around the Amplify lesson:** over-filtering kills funnel. Classifier is intentionally loose — default-include, only filter clear junk.

## How it works

```
config/subreddits.yaml + keywords.yaml
            │
            ▼
   reddit_scraper.py      ── HTTP JSON, no auth needed
            │
            ▼
   classifier.py          ── Claude pass: loose relevance scoring
            │                (default INCLUDE unless clear junk: job ad,
            │                 promo, bot, totally unrelated)
            ▼
   drafter.py             ── Claude pass: drafts personalized email
            │                quoting THEIR actual post/comment
            ▼
   SQLite (state/db.sqlite)
            │
            ▼
   samples/drafts/*.eml   ── Human reviews before any send
            │
            ▼
   sender.py              ── Gmail SMTP (DISABLED until you flip flag)
```

## Decisions baked in (2026-05-19)

- **Sender:** `hiimalexllc@gmail.com` (Gmail) — not `alex@hiimalex.ai`. Better deliverability on a warmed-up Gmail than a brand-new domain.
- **SMTP:** Gmail SMTP via app password (free, 500/day soft limit). Resend was the runner-up if Gmail rep takes a hit.
- **Source:** Reddit only for v1. LinkedIn comes later if the cadence converts.
- **Filter strategy:** OPEN — match ANYTHING remotely relevant. Avoid the Amplify over-filter trap.
- **ICP:** Split test — finance/hedge-fund + broad AI-curious. Two persona prompts, separate stats.
- **Video:** NOT in pipeline. Alex personally records Looms once we have prospects to film for.
- **Runtime:** Local laptop, manual run. Not deployed. Move to Railway later if useful.
- **Storage:** SQLite (`state/db.sqlite`) — committed to repo (no PII concerns, public Reddit data).

## Setup

```bash
cd hi-im-alex-outreach

# Python 3.9+ (system Python on macOS works)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy env template, fill in ANTHROPIC_API_KEY
cp .env.example .env
# Edit .env — only ANTHROPIC_API_KEY is required for POC
```

## Usage

```bash
# 1. Scrape Reddit (no Reddit creds needed — uses public JSON)
python3 -m src.cli scan --limit 50

# 2. Classify scraped posts (Claude, loose threshold)
python3 -m src.cli classify

# 3. Draft personalized emails for qualified prospects
python3 -m src.cli draft

# 4. View prospects + drafts
python3 -m src.cli status
ls samples/drafts/

# 5. Full pipeline (scan + classify + draft) in one go
python3 -m src.cli run
```

## What's stubbed for v1

- **Hunter.io enrichment** (`src/enricher.py`) — TODO. For Reddit POC, we capture the Reddit handle + post URL. Email lookup happens later when Alex decides to actually reach out.
- **Gmail SMTP send** (`src/sender.py`) — code is written but the `--really-send` flag is required AND defaults to `False`. POC drafts only.
- **Cadence runner** (touch 2/3/4) — not built. Re-evaluate after first batch of drafts.

## How to review POC output

1. Run `python3 -m src.cli run --limit 50`
2. Open `samples/prospects.json` → see what Reddit threads/comments matched
3. Open `samples/drafts/*.eml` → see what emails Claude would draft
4. **Verdict:** are these real prospects? Would these emails get a reply?

If yes → wire enrichment + send. If no → adjust prompts in `src/prompts.py` and re-run.

## Files

```
hi-im-alex-outreach/
├── PLAN.md              — original outreach automation plan
├── README.md            — this file
├── requirements.txt
├── .env.example
├── .gitignore
├── config/
│   ├── subreddits.yaml  — 15+ broad subreddits (anti-overfilter)
│   ├── keywords.yaml    — 16 loose keywords
│   └── persona.yaml     — Alex's pitch context for drafter
├── src/
│   ├── cli.py           — click CLI: scan / classify / draft / send / status / run
│   ├── db.py            — SQLite schema + helpers
│   ├── reddit_scraper.py
│   ├── classifier.py    — Claude loose-relevance pass
│   ├── drafter.py       — Claude email-drafting pass
│   ├── enricher.py      — Hunter.io stub
│   ├── sender.py        — Gmail SMTP (off by default)
│   └── prompts.py       — system prompts
├── state/               — SQLite DB lives here (gitignored)
└── samples/             — POC output for review (gitignored)
```
