# Erasure vs. DROP vs. DeleteMe

**TL;DR.** California's DROP is a one-shot deletion request. Erasure makes DROP *stick*.

---

## What DROP does

On Jan 1, 2026, the California Privacy Protection Agency launched DROP (Delete Request and Opt-Out Platform) at [privacy.ca.gov/drop](https://privacy.ca.gov/drop). One form, one submission, 545+ registered CA data brokers get the request. Enforcement starts August 1, 2026 — $200/day per violation, no cure period.

215,000 Californians signed up in the first 7 weeks.

## What DROP does not do

DROP is a firehose. It sends the request and returns a confirmation code. It does not:

1. **Verify** that any broker actually deleted your data.
2. **Cover** the long tail of brokers that are not yet CA-registered.
3. **Produce evidence artifacts** you can attach to a CPPA complaint if a broker ignores the request.
4. **Work outside California** — DROP requires CA residency via the state identity gateway.

## What Erasure does

Erasure is an open-source CLI that runs *around* DROP to fill those gaps:

| Step | DROP | Erasure |
|------|------|---------|
| Submit deletion request to 500+ brokers | ✅ (primary path) | Wraps DROP for CA users |
| Baseline screenshot evidence before DROP | — | ✅ `erasure scan` |
| Re-scan at day 45 / 90 | — | ✅ `erasure verify` |
| Flag non-compliant brokers | — | ✅ persistent matches in diff |
| HTML evidence report for CPPA complaint | — | ✅ `erasure report` |
| Cover non-CA-registered long tail | — | Roadmap |
| Works for non-CA residents | — | Roadmap (per-broker adapters) |

## Why this matters

CalPrivacy has a Data Broker Enforcement Strike Force. Fines already issued:

- S&P Global — $62,600 for failing to register
- Datamasters — $45,000 for selling health data lists
- ROR Partners — $56,600 for profiling 262M Americans unregistered

After August 1, 2026, registered brokers must check DROP every 45 days and process deletions within 90 days. Someone has to verify they actually did. Erasure is that check.

## DeleteMe, Incogni, Optery

DeleteMe charges $129/yr to submit deletion requests on your behalf. That was worth it before DROP — manually filing 500+ opt-outs is a lot of work. With DROP, the submission step is already free and automatic for Californians.

The remaining value is in **verification and evidence**, which paid services don't expose as artifacts. Erasure is:

- **Open source** (MIT) — inspect what it does, run it yourself
- **Free** — no subscription
- **Evidence-first** — every scan produces screenshots and HTML snapshots a lawyer could use
- **DROP-native** — designed around California's legal framework, not around the old per-broker maze

## Social launch angles (for the thread)

1. *"California built the kill switch. Here's how to prove they actually pulled the trigger."*
2. *"DROP is free. So is the tool that verifies DROP worked."*
3. *"Persistent matches after 90 days = $200/day/violation. Erasure finds them."*
4. *"Not a DeleteMe competitor. A DROP supplement."*

## Status (2026-04-19)

- `erasure init` — interactive profile builder ✅
- `erasure drop recon|submit|status` — CA DROP portal client (selectors pending first live recon)
- `erasure scan` — baseline evidence scan ✅
- `erasure verify` — diff baseline vs follow-up ✅
- `erasure report` — HTML evidence output ✅
- 586 brokers loaded (542 CA-registered)

**Next:** First live DROP recon → map form selectors → one real end-to-end submission → 45-day verify → publish report as launch proof.
