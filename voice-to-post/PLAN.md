# Voice Memo → Post Pipeline — PLAN

**Status:** Bare-bones plan (2026-05-19). Not built. **Blocked on `linkedin-content-engine/` being functional first** — that project owns the swipe file mirror this pipeline feeds into.

## What this is
Voice memo → transcription → 3 LinkedIn post variants → pick one → lands in the swipe file → publishes on next slot.

## Why
Alex has post-worthy ideas mid-day (scuba diving, conversations, walks). Voice memo = lowest-friction capture. Sitting down at a laptop to convert into a post is the bottleneck.

## Architecture

```
iPhone Voice Memos app
    │
    └── iOS Shortcut (share sheet target)
            │
            └── POST audio (m4a) to Railway endpoint
                    │
                    ├── Groq Whisper transcription
                    │
                    ├── Claude pass with "Alex's LinkedIn voice" prompt
                    │       │
                    │       └── outputs 3 variants — scroll-stopping, single-block
                    │           (single spaces, no line breaks — per LinkedIn copy quirk)
                    │
                    └── Telegram message to Alex via JARVIS:
                            - "Pick 1, 2, 3 or skip"
                            - variants inline
                                │
                                └── On pick → write to swipe file
                                              via linkedin-content-engine
                                              + tag "voice-origin"
                                              + queue for next publish slot
```

## Tech stack (proposed)
- Railway service (Node or Python — match linkedin-content-engine)
- Groq Whisper API (cheapest transcription)
- Anthropic SDK
- Existing JARVIS Telegram bot for delivery
- Notion API write (via linkedin-content-engine module)

## Build order
1. (Wait for linkedin-content-engine to expose a `addToSwipeFile()` API)
2. Railway endpoint: receive audio, run Whisper, run Claude variants, return JSON
3. JARVIS integration: deliver variants to Telegram, accept callback for pick
4. iOS Shortcut: audio → endpoint, with auth token
5. Closed loop: feed performance data from linkedin-content-engine back into the variant prompt over time

## Dependencies on other projects
- `linkedin-content-engine/` — REQUIRED (owns the swipe file)
- `jarvis/` — Telegram delivery surface

## Open questions
- Groq Whisper quality on noisy audio (walking, beach, gym)?
- Should the 3 variants be visibly different angles (hook style A/B/C) or 3 polished takes of the same angle?
- Auto-publish on pick, or land in swipe file and let the existing publish cadence pick it up?
