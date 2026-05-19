# LinkedIn Content Engine — PLAN

**Status:** Bare-bones plan (2026-05-19). Not built.

## What this is
Pipeline for Alex's ~120-post Notion swipe file. Owns:
- Notion ↔ local mirror of the swipe file
- Publish tracker (record URL + timestamp on each publish)
- 7-day performance evaluator (Claude reviews metrics, suggests rewrite / archive / re-post)
- Comments-on-MY-posts monitor (draft replies, push to Telegram for approval)

## What this is NOT
- Commenting on OTHERS' posts → that's `amplify/` (currently broken, rebuild decision pending)
- Outreach to prospects → that's `hi-im-alex/outreach-automation/`
- Voice memo → post → that's `voice-to-post/` (depends on this project)

## Architecture

```
Notion swipe file (source of truth, 120 pages)
    │
    ├── Notion sync ──→ local SQLite cache  (./db/swipe.sqlite)
    │
    ├── Publish tracker ──→ scrape metrics 7 days post-publish
    │       │            (chrome-mcp authenticated session)
    │       └── writes back to Notion page as new "performance" entry
    │
    ├── Weekly evaluator ──→ Claude pass over 7-day-old posts
    │       │
    │       └── output per post:
    │            - top quartile  → tag "re-post 90 days"
    │            - bottom quart  → tag "archive"
    │            - middle        → tag "rewrite" + suggestion
    │
    └── Comment monitor ──→ poll my profile for new comments on my posts
            │
            └── draft reply in my voice
                  │
                  └── send via JARVIS Telegram → I approve/edit/skip
```

## Tech stack (proposed)
- Node or Python (Python preferred — matches health-insights, world3-dashboard)
- SQLite for local mirror
- Notion API (official SDK)
- Anthropic SDK (Claude evaluator + reply drafter)
- chrome-mcp for LinkedIn metric scraping (LinkedIn API is restrictive)
- Re-use JARVIS Telegram surface for approval flow

## Build order
1. Notion schema discovery — what does the swipe file actually look like
2. Notion → SQLite one-way sync
3. Publish-tracker (manual paste of post URL first, cron metric scrape after)
4. Evaluator (offline, no posting yet)
5. Comment monitor + JARVIS Telegram approval

## Dependencies on other projects
- JARVIS (Telegram surface) — already live
- Voice-to-Post — does NOT depend on this; it's the reverse

## Open questions
- Does LinkedIn return enough metrics via authenticated browser scrape? Profile-visit attribution is the hard one.
- Notion API rate limits with 120-page swipe file + weekly evaluator passes?
- Should the evaluator's rewrite suggestions land back in Notion or stay in SQLite + surface via dashboard?
