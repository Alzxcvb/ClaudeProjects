"""Account-exposure scanning via the Sherlock OSINT tool.

Wraps the external `sherlock` binary (install via `pipx install sherlock-project`)
and normalizes its output into the same `state/` layout as broker scans so the
dashboard can render it alongside DROP receipts and broker evidence.
"""
