# Hi I'm Alex — Outreach Automation — PLAN

**Status:** Building (2026-05-19). This is priority #1 — the single revenue lever for Hi I'm Alex consulting.

## What this is
A personalized cold-outreach pipeline for Hi I'm Alex consulting. Targets people who comment on relevant LinkedIn posts or Reddit threads about AI / consulting / automation pain points. Sends them a short personalized video pitch that opens with a 2-3 sec capture of THEIR own comment or profile, then transitions into a 7-8 sec canned pitch with their name overlaid.

## Why this is priority #1
- Hi I'm Alex has been live ~1 month
- Landing page + LinkedIn presence both built
- **Zero clients yet**
- Outreach is the missing distribution layer
- Pattern reference: a similar video-personalization approach reportedly hit ~10% reply rate vs ~1-2% for normal cold outreach

## Architecture (4 stages)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 1 — PROSPECT IDENTIFICATION                                       │
│                                                                         │
│   LinkedIn (via chrome-mcp authenticated session)                       │
│   Reddit  (public API + scrape)                                         │
│                                                                         │
│   Find: comments under posts that match keyword/pain-signal filters     │
│          (e.g. "drowning in repetitive work", "need AI but don't know   │
│          where to start", "automate this", "AI for finance/research")   │
│                                                                         │
│   Output: prospects table {name, comment_text, comment_url,             │
│                            profile_url, source_post_url, captured_at}   │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 2 — CONTACT ENRICHMENT                                            │
│                                                                         │
│   For each prospect: find email via                                     │
│      - Hunter.io (cheapest)                                             │
│      - Apollo.io                                                        │
│      - Clay (most flexible, ~$149/mo, enriches w/ company data too)     │
│                                                                         │
│   Output: prospects table extended with {email, company, role,          │
│                                          enriched_at, confidence}       │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 3 — PERSONALIZED VIDEO PITCH                                      │
│                                                                         │
│   Opening 2-3 sec:                                                      │
│      Screen capture of THEIR comment OR profile                         │
│      (Puppeteer + ffmpeg for DIY, or Bhuman.ai handles this)            │
│                                                                         │
│   Body 7-8 sec:                                                         │
│      Pre-recorded video of Alex pitching consulting services            │
│      with their NAME overlaid                                           │
│      (Bhuman.ai or Tavus for AI lip-sync personalization)               │
│                                                                         │
│   Output: hosted video URL per prospect                                 │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 4 — EMAIL + FOLLOW-UP CADENCE                                     │
│                                                                         │
│   Touch 1: "Saw your comment on X — made me think of [service].         │
│             10-sec video for you: [link]"                               │
│   Touch 2 (+3 days): bump                                               │
│   Touch 3 (+5 days): value-add (case study / template)                  │
│   Touch 4 (+7 days): breakup                                            │
│                                                                         │
│   Via Instantly.ai or Smartlead (handles deliverability + warmup)       │
│                                                                         │
│   Output: replies routed to Alex's inbox                                │
└─────────────────────────────────────────────────────────────────────────┘
```

## Two paths — DECISION NEEDED

### Path A — SaaS-stitched (RECOMMENDED for v1)
- **Clay** ($149-349/mo) — prospect enrichment + Apollo/Hunter integration + custom enrichment columns + webhook out
- **Bhuman.ai** ($59-99/mo) — personalized video stitch (opening capture + pitch body)
- **Instantly.ai** ($37-97/mo) — email cadence + deliverability + inbox warmup
- **Glue code** — minimal — webhooks between them, plus a Notion/Google Sheet for prospect QA
- **Total recurring:** ~$250-550/mo
- **Build time:** 1-2 weeks
- **Pros:** working in days, focus on prospect quality + pitch script (the things that actually matter)
- **Cons:** monthly recurring before any revenue, less control

### Path B — Full DIY
- Build Stages 1-4 from scratch
- LinkedIn comment scrape via existing `chrome-mcp`
- Reddit via public API
- Email finding via Hunter API only ($49/mo)
- Video generation: Puppeteer + ffmpeg for the opening, pre-recorded clips for the body, manual ffmpeg stitch
- Email cadence: SMTP via Resend ($20/mo) + custom queue
- **Total recurring:** ~$70/mo + dev time
- **Build time:** 2-3 months
- **Pros:** full control, no SaaS lock-in, you learn the stack
- **Cons:** slow path to revenue, video pipeline is non-trivial (lip-sync personalization is hard)

### Path C — Hybrid (compromise)
- Stages 1, 4: DIY (cheap, easy)
- Stage 2: Clay (the painful part — enrichment is genuinely hard)
- Stage 3: Bhuman (video personalization is genuinely hard)
- **Total recurring:** ~$200/mo
- **Build time:** 2-3 weeks

## Build order (path-agnostic)
1. Prospect-source decision: LinkedIn only / Reddit only / both
2. Pitch script for the canned video body (this is the lever that actually matters — write it before any tooling)
3. ICP keyword list (what comments are worth chasing)
4. Stand up Stage 1 — get 50 real prospects in a table to QA
5. Stand up Stage 2 — get emails for ~30 of them
6. Stand up Stage 3 — record the pitch body video, generate first 10 personalized videos
7. Stand up Stage 4 — first cohort send
8. Iterate on prospect quality + pitch + subject line based on reply rates

## Open decisions (will ask Alex)
1. Path A vs B vs C
2. Prospect source for v1: LinkedIn only, Reddit only, or both
3. ICP keyword direction: finance/hedge-fund pain (per existing ICP) OR broader AI-curious (more volume)?

## What this is NOT
- Commenting on others' posts to get on their radar → that's Amplify (broken)
- Posting MY OWN content → that's `linkedin-content-engine/` (planned)
- DM outreach on LinkedIn → out of scope for v1 (LinkedIn rate limits aggressive automation)
