# LinkedIn Content Engine — PLAN

**Status:** Phase 1.5 shipped (2026-07-10) — SQLite content CRM (`./crm` + `content.db`: ideas / variants / runs / metrics), posts.jsonl migrated, recycling queue + comparability gates live, generator/predictor rewired to the db. See [`README.md`](README.md) and [`RUNBOOK.md`](RUNBOOK.md). Phase 2 (chrome-mcp scrape) remains to do. The measurement discipline below (§0–§6) is unchanged and still governs.

**Prior status:** Phase 0 shipped (2026-05-30) — `generate.py` + `predict.py` + `posts.jsonl` seeded with the first 3 posts.

**Original status:** Bare-bones plan (2026-05-19).

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

---

# Experimentation & Measurement Layer (added 2026-05-25)

This section is the "track what works / what doesn't / what to A/B test" methodology. The architecture above is the plumbing; this is what makes the plumbing teach us anything.

## 0. The honest statistical reality (read this first)

At 3–7 posts/week, **you cannot run rigorous, p-value A/B tests on most variables.** N is too small, noise is too high, and every post is confounded by time-of-day, day-of-week, follower count at post time, first-post-of-day algorithm boost, and topical luck. Anyone selling you "data-driven LinkedIn A/B testing" at this volume is selling noise.

So the method is **structured logging → directional learning → occasional clean head-to-head tests on big-effect variables.** Not significance chasing.

**Concrete cautionary example (live right now):** the two posts scheduled 2026-05-25 — short variant in ~1h (afternoon), long variant tomorrow morning — are NOT a clean test. Posting them at different times of day means time-of-day is fully confounded with copy length. If the long one wins, we won't know if it was the copy or the slot. This is exactly the trap the method below is designed to avoid: a real head-to-head holds everything constant except the one variable under test.

## 1. The real lever: pre-registered metadata (tag BEFORE posting)

You cannot attribute performance to "hook style" or "topic" after the fact. Every post must carry structured attributes recorded *before* it goes live. **This is the discriminating step — most "I tracked my posts" attempts fail here, not at scraping.** Add these as Notion properties on each swipe-file page:

| Property | Values (controlled vocab) |
|---|---|
| `hook_archetype` | contrarian-take · story-open · stat-shock · question-open · "most people don't realize" · how-to promise |
| `format` | long-form-story · short-punchy · listicle · hot-take · how-to/teaching |
| `word_count` | auto-computed bucket: <100 / 100–200 / 200–350 / 350+ |
| `topic_cluster` | AI-capability · future-of-work · build-in-public · client-outcome · personal/meta |
| `cta_type` | engagement-question · link-in-comment · soft-teach · direct-book · none |
| `media_type` | none · single-image · carousel · video/GIF · screenshot |
| `post_dow` | Mon–Sun (auto) |
| `post_slot` | early-AM · mid-AM · midday · afternoon · evening (auto from timestamp) |
| `followers_at_post` | int (captured at publish) |
| `origin` | swipe-file · voice-memo · news-reaction · original |

The evaluator later groups by these to find directional patterns ("story-opens average 2.3× the conversion score of stat-shocks over the last 20 posts"). Without pre-registration this analysis is impossible.

## 2. Score conversion, not vanity metrics

The goal is **consulting inquiries, not engagement.** A post with 10K impressions and 0 bookings is worse than 500 impressions and 1 booking. Engagement-farm hooks ("comment 'AI' and I'll DM you") win impressions and lose clients — we must NOT optimize for them.

Starter weighted score (tune as data arrives):

```
score = 100·bookings + 10·site_clicks + 5·profile_visits
      + 4·reposts + 3·comments + 1·reactions + 0.01·impressions
```

Also track **conversion efficiency = score ÷ impressions** so a small-but-mighty post isn't buried under a viral-but-useless one. Report both raw score and efficiency.

### The hard part: instrumenting clicks + bookings (LinkedIn won't give you these)
LinkedIn shows impressions/reactions/comments but NOT who clicked through or who booked. Close the loop yourself:
- **Per-post tracked link.** Put a unique URL in the first comment per post — either a `hiimalex.ai/?utm_campaign=post_<id>` UTM or (better, since Cloudflare Web Analytics is weak on UTMs) a per-post redirect slug you own (e.g. `hiimalex.ai/p/<id>` → 302 to site). Unique slug = unambiguous per-post click count.
- **Booking attribution.** Add a required Calendly screening question: "Where did you find me?" (free text or dropdown incl. "LinkedIn post"). That's the only reliable post→booking link. Manually stamp the booking back onto the post's Notion row.
- **Profile visits** are only available as a noisy weekly aggregate on LinkedIn — treat as a soft signal, never attribute to a single post.

## 3. Capture cadence: 3 checkpoints, not 1

The existing plan scrapes once at T+7d. Capture at **T+24h, T+72h, T+7d** instead. Velocity matters:
- `velocity_24h = impressions@24h ÷ impressions@7d` — high velocity = algorithm picked it up fast; low-and-climbing = slow burn. Lets you spot duds vs slow-burners early and decide whether to boost (comment, reshare) while it's still live.
- Final score uses the T+7d snapshot.

## 4. What's actually worth A/B testing (big effect sizes only)

Only test variables big enough to beat the noise floor. **Decidable at this volume:**
- long-form-story **vs** short-punchy
- generic thought-leadership **vs** specific client-story
- with-CTA **vs** without-CTA
- with-image/video **vs** text-only
- link-in-comment **vs** link-in-post (reach penalty test)

**Not worth testing** (noise will eat any signal): emoji placement, exact word count, single hashtags, one-word hook tweaks.

### Clean test protocol (so a result means something)
1. Change **exactly one** variable; hold format, topic, length, media constant.
2. Post the two variants **same day-of-week, same time slot, one week apart** (e.g. two consecutive Tuesday 8am slots). This neutralizes the time-of-day confound that wrecks the current 2-post setup.
3. Pre-register the hypothesis + which metric decides it (usually conversion-efficiency, sometimes raw reach).
4. Require a **big** gap to call it (e.g. >40% on the decision metric). Anything closer = "inconclusive, noise" — do NOT act on it.
5. Best-of-3 over a month beats one-shot. One head-to-head per month is plenty.

## 5. Phasing — do NOT build the whole pipeline first

**Phase 0 (SHIPPED 2026-05-30, ~1.5 hrs):**
- `generate.py` (Sonnet 4.6): topic + notes → 3 variants varying ONE controlled axis (default `hook_archetype`). Pulls last 10 posts from `posts.jsonl` as few-shot — so the prompt evolves as the history grows, no manual tuning.
- `predict.py` (Haiku 4.5): variant → comparative score (`BEAT`/`MATCH`/`UNDERPERFORM` median) + numeric forecast with explicit `LOW-N` confidence tag until n ≥ 10.
- `posts.jsonl`: append-only post log, seeded with the 3 already-shipped posts (post-001 short / post-002 long head-to-head + post-003 hackathon). Metadata fields from §1 baked in (format, hook_archetype, word_count, cta_type, hashtags, actuals).
- Prompts in `prompts/generator.md` + `prompts/predictor.md` — plain markdown, editable, version-controlled.

**Phase 1 (next, 1–2 days):**
- `log.py` CLI: append a new row to `posts.jsonl` from a single command (no manual JSON pasting).
- `retro.py` CLI: weekly retro — prediction-vs-actual table, surface where the predictor was wrong, suggest changes for Alex to fold into `prompts/*.md` (NOT auto-mutate — risky).
- Per-post tracked link (`hiimalex.ai/p/<id>` 302 redirect) so click-through is countable.
- Manual metric entry at the 3 checkpoints (24h, 72h, 7d) — copy 3 numbers off the post's "View analytics".
- Retro-log the two 2026-05-25 posts as the first two rows (note the time-of-day confound on them). **DONE — posts-001, -002 seeded.**

**Phase 2 (automate capture):** chrome-mcp scrapes the 3 checkpoints automatically via the authenticated session (use `chrome_evaluate`, not `chrome_snapshot` — snapshot is useless on LinkedIn per `reference-chrome-mcp.md`). ⚠️ Risk: scraping your own analytics page repeatedly is lower-risk than prospecting, but still respect human-like cadence; this is read-only on your own posts so detection risk is low but non-zero.

**Phase 3:** wire the evaluator's "run this test next" output into the voice-to-post variant generator so the system proposes the next experiment automatically (closes the loop with `voice-to-post`).

## 6. Weekly evaluator output (what Claude actually produces)
Once ≥10 posts are logged, the weekly pass emits:
1. **Leaderboard** by conversion score AND by efficiency (top 3 / bottom 3).
2. **Directional reads** grouped by each metadata dimension ("question-open hooks: avg efficiency 0.18; stat-shock: 0.09 — lean into questions"). Always caveat n.
3. **Re-post candidates** (top-quartile, >90 days old).
4. **One proposed A/B test** for next week, with the §4 clean protocol pre-filled.
5. **Confounders flagged** (e.g. "your best post also had 2× normal followers that week — discount it").
