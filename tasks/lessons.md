# Lessons

Patterns learned from corrections during past sessions. Reviewed at session start.
Updated after any correction from the user.

---

<!-- Add entries below as lessons are learned. Format:
## [date] — [short title]
**Mistake:** What went wrong.
**Correction:** What the user said.
**Rule:** What to do differently going forward.
-->

## 2026-05-20 — CTA must match the live offer end-to-end
**Mistake:** Drafted the Hi I'm Alex launch post promising a "free 15-minute fit call," but the actual landing page (hiimalex.ai) only offers a paid $200 90-min call. Shipped a free→paid funnel mismatch + a double CTA (free call AND $200 Quick Start at once). I'd flagged the final CTA-line mismatch but left the "free" promise in the body.
**Correction:** Alex pointed out the link goes to the $200 paid call and asked why it wasn't a 10/10.
**Rule:** Before finalizing marketing copy, confirm the exact bookable offer (price/duration/free-vs-paid, the event that actually exists in Calendly/Stripe) and make EVERY mention in the draft consistent — not just the link line. One next-action per CTA; don't stack free + paid. Name the deliverable ("$200, leave with Claude running"), not "discovery call."

## 2026-06-03 — "Prospecting" means NEW reach; never auto-ship low-value while gating the real ask
**Mistake:** Asked to "continue work on linkedin prospecting." I spent the session re-messaging the 5 already-accepted connections with templated value-first thank-yous (personalized opener, but identical AI-tip body + "happy to send the prompt" close across all 5 = reads as bot spam), AND auto-sent those without a final gate. Then I put the actual NEW outreach (13 NY invites) BEHIND an approval gate and walked. Net result Alex returned to: 0 new prospects, 5 canned DMs to warm contacts. Priority was exactly inverted — auto-shipped the low-value maintenance task, blocked the high-value primary task.
**Correction:** "doesn't look like you reached out to any new people but you messaged all the old ones again with some generic garbage bullshit, why the fuck did you do that?!"
**Rule:** (1) When Alex says "prospecting," the default deliverable is NEW connections, not warm-contact maintenance. Lead with new reach; treat thank-yous/follow-ups as optional secondary, never the bulk of a session. (2) Never auto-execute the secondary/low-value action while gating the primary/high-value one — if anything gets a gate, gate the bigger/irreversible thing and just-do the rest, not the reverse. (3) Templated outreach sent to N people with the same body/close is "generic garbage" no matter how personalized the first line — if I can't make each message genuinely specific, don't send it. (4) Acceptance via an AskUserQuestion option is not a license to ship mediocre execution; the quality bar still applies.

## 2026-06-03 — Verify real git HEAD before building; memory is point-in-time
**Mistake:** On a `--resume` into a fresh context, I trusted the 42-day-old Erasure memory that said HEAD was `2af0d54` and started re-building the `legal/` module from scratch. A prior/parallel session had actually moved HEAD two commits ahead (`f5ad0eb` + `ad0ffd0`) and already built that exact module. My re-implementation overwrote committed files (`legal/templates.py`, `legal/__init__.py`, `test_legal.py`) and added a duplicate CLI group, breaking the build.
**Correction:** Self-caught when CLI tests failed with "No such command" (a second `legal` group had shadowed mine), then traced it to pre-existing commits.
**Rule:** (1) Before writing ANY new code in a project, run `git log --oneline -5` + `git status` to learn the true current state — never trust a memory file's commit hash or "what's shipped" claims as live (the memory header even warns they're point-in-time). (2) In the shared `ClaudeProjects` parent repo, assume a parallel session may have committed or staged work since the memory was written; reconcile against real HEAD first. (3) Recovery for an overwrite of committed files: `git restore <path>` from the index (preserves others' staged work) rather than blunt `git checkout HEAD -- .`, then delete only your own untracked additions. It worked cleanly here with zero data loss.
