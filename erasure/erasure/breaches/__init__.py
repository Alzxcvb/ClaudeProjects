"""Data-breach exposure checks via the HaveIBeenPwned API.

Calls HIBP's `/breachedaccount/{email}` endpoint directly (no subprocess —
HIBP is a plain HTTPS service). An API key is required; set `HIBP_API_KEY`
in the environment. Results are persisted as a `BreachesManifest` in
`state/breaches/` so the dashboard can render them alongside broker scans
and Sherlock account hits.
"""
