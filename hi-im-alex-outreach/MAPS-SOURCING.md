# Maps Sourcing — Google Maps as an ICP-discovery layer for Prospector

**Status:** built 2026-06-21. Decided in idea-ranker `TEST-RUN-017-hatim-toor-gmaps-email-scraper.md`.

## What this is

A thin layer that turns a Google Maps export into a ranked list of small,
owner-operated service businesses that match the Hi I'm Alex ICP. It feeds the
existing LinkedIn workstream. It is the "OTHER half" of Prospector that the
resume doc flagged as planned but not built.

## What this is NOT

1. **Not a scraper.** We do not build or run a Maps scraper. Buy the export from
   an off-the-shelf Apify actor. A custom scraper is a maintenance treadmill
   (endpoint changes, captchas, proxies) and a ToS-ban risk to our own infra,
   for data that rents for a few dollars.
2. **Not an email blaster.** Maps gives a website and sometimes an email. Those
   are for finding and qualifying the business and its owner, not for bulk cold
   email. Mass-emailing scraped lists fights the personalized model, burns the
   sending domain we rely on for the real funnel, and carries compliance risk
   (CAN-SPAM, plus stricter consent rules for EU sole-traders). Outreach stays
   LinkedIn-first and personalized.

## The flow

```
Apify Google Maps export (CSV/JSON)
        |
        v
  src/maps_ingest.py        rank against config/maps_icp.yaml, dedup, score
        |
        v
  prospects/sources/maps_worklist_<city>_<date>.md     <-- the intake
        |
        v
  chrome-mcp -> find owner on LinkedIn (finder link is in each row)
        |
        v
  write a personalized note off their real headline (Barney method)
        |
        v
  send via the standard custom-invite flow -> log in SENT_LOG.md
        |
        v
  python3 prospects/build_tracker.py   seeds tracker.csv as usual
```

The Maps layer stops at the worklist. From there it is the same LinkedIn motion
already documented in `prospects/RESUME-prospector.md`.

## Step 1 — buy the export

Pick one Apify actor, run it for a city + category, download CSV or JSON:

- `compass/crawler-google-places` — core listing data (name, category, website,
  phone, rating, reviews, maps url).
- `lukaskrivka/google-maps-with-contact-details` — same, plus website-scraped
  emails/socials. Only worth it if you want the email for owner-confirmation.

Search the actor by category + city, e.g. "bookkeeping services in Austin TX".
Pull a few hundred rows; the ranker trims to the real fits.

## Step 2 — rank it

```bash
python3 src/maps_ingest.py <export.csv|json> --city "Austin, TX" --top 30
```

Reads `config/maps_icp.yaml` (edit the category allow/skip lists and thresholds
to taste). Tolerant of the different column names the actors use. Outputs to
`prospects/sources/` (gitignored, local-only, since it holds business contact
data):

- `maps_candidates_<city>_<date>.csv` — every kept row, ranked, with a fit score.
- `maps_worklist_<city>_<date>.md` — the top N as an actionable checklist, each
  with a `site:linkedin.com/in` finder link to locate the owner fast.
- `maps_seen.csv` — dedup ledger keyed by business + city. Re-running on a fresh
  or overlapping export only ever adds genuinely new businesses, so you can pull
  monthly without re-importing the same places.

## Step 3 — work the list (existing motion)

For each fit in the worklist: open the finder link, find the owner's LinkedIn,
fill in name + slug + a note angle from their real headline, send via the
standard flow, log it in `SENT_LOG.md`, then re-seed the tracker. Same cap
discipline (daily 15 to 20, rolling 100 per 7 days) as the rest of Prospector.

## Why ranking instead of raw list

The pitch lands on owner-operated businesses that are active but not chains, with
a real website (a findable owner) and a decent reputation (likelier to value
tooling). The score rewards exactly that shape so you work the best fits first
instead of grinding a raw dump. Tune `config/maps_icp.yaml` per geo as you learn
which categories actually accept and reply.
