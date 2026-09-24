"""Route a question to a destination. v1 always routes to the council; this
is the hook a future Jev gate can plug into (see brief-council.md, "Out").
"""
from __future__ import annotations


def route(question: str) -> str:
    """Return the destination for a question. v1 always returns "council"."""
    return "council"
