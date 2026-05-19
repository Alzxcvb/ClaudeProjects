"""Claude pass that decides include/exclude + persona + relevance score."""
from __future__ import annotations
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

import anthropic

from . import db
from .prompts import CLASSIFIER_SYSTEM

MODEL = os.environ.get("CLASSIFIER_MODEL", "claude-haiku-4-5-20251001")


def _extract_json(text: str) -> dict:
    # Strip code fences if present
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def classify_one(client: anthropic.Anthropic, prospect: dict) -> dict:
    user_msg = (
        f"Subreddit: r/{prospect.get('subreddit')}\n"
        f"Title: {prospect.get('post_title')}\n"
        f"Body:\n{prospect.get('post_body') or '(empty)'}\n"
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=CLASSIFIER_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = resp.content[0].text
    try:
        return _extract_json(raw)
    except Exception as e:
        return {"include": False, "relevance": 0, "persona": None,
                "reason": f"parse_error: {e}: {raw[:100]}"}


def classify_pending(limit: int = 50) -> dict:
    client = anthropic.Anthropic()
    conn = db.connect()
    pending = db.unclassified(conn, limit=limit)
    summary = {"processed": 0, "included": 0, "excluded": 0, "errors": 0,
               "finance": 0, "broad": 0}
    for row in pending:
        verdict = classify_one(client, dict(row))
        now = datetime.now(timezone.utc).isoformat()
        included = bool(verdict.get("include"))
        relevance = int(verdict.get("relevance") or 0)
        persona = verdict.get("persona") if included else None
        filter_reason = None if included else (verdict.get("reason") or "excluded")
        db.mark_classified(conn, row["id"], relevance, persona, filter_reason, now)
        summary["processed"] += 1
        if included:
            summary["included"] += 1
            if persona == "finance":
                summary["finance"] += 1
            elif persona == "broad":
                summary["broad"] += 1
        else:
            summary["excluded"] += 1
        if "parse_error" in (verdict.get("reason") or ""):
            summary["errors"] += 1
        print(f"  [{row['id']}] r/{row['subreddit']} include={included} "
              f"rel={relevance} persona={persona} — {verdict.get('reason','')[:80]}")
    return summary
