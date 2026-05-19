"""Claude pass that drafts a personalized cold email for a qualified prospect."""
from __future__ import annotations
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import anthropic
import yaml

from . import db
from .prompts import DRAFTER_SYSTEM

MODEL = os.environ.get("DRAFTER_MODEL", "claude-sonnet-4-6")

ROOT = Path(__file__).resolve().parent.parent
PERSONA_PATH = ROOT / "config" / "persona.yaml"
SAMPLES_DIR = ROOT / "samples" / "drafts"


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _persona_block(persona: Optional[str]) -> str:
    with open(PERSONA_PATH) as f:
        cfg = yaml.safe_load(f)
    p = cfg["ideal_clients"].get(persona) or cfg["ideal_clients"]["broad"]
    return (
        f"PERSONA: {persona}\n"
        f"Persona description: {p['description']}\n"
        f"Typical pains this persona has that Alex solves:\n  - "
        + "\n  - ".join(p["pain_examples"]) + "\n"
        f"\nWhat Alex does (use to write the second sentence):\n{cfg['what_alex_does']}\n"
        f"\nCalendly: {cfg['sender']['calendly']}\n"
    )


def draft_one(client: anthropic.Anthropic, prospect: dict) -> dict:
    persona_block = _persona_block(prospect.get("persona"))
    user_msg = (
        persona_block
        + f"\n--- PROSPECT POST ---\n"
        f"Subreddit: r/{prospect.get('subreddit')}\n"
        f"Title: {prospect.get('post_title')}\n"
        f"Body:\n{prospect.get('post_body') or '(empty)'}\n"
        f"Reddit handle: u/{prospect.get('handle')}\n"
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=DRAFTER_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = resp.content[0].text
    try:
        return _extract_json(raw)
    except Exception as e:
        return {"subject": "(parse error)", "body": f"PARSE ERROR: {e}\n\nRAW:\n{raw}"}


def _write_sample(prospect: dict, draft: dict) -> Path:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    handle = prospect.get("handle", "unknown").replace("/", "_")
    path = SAMPLES_DIR / f"{prospect['id']:04d}_{handle}.eml"
    path.write_text(
        f"X-Reddit-Source: {prospect['post_url']}\n"
        f"X-Persona:       {prospect.get('persona')}\n"
        f"X-Relevance:     {prospect.get('relevance')}\n"
        f"Subject: {draft.get('subject', '')}\n"
        f"\n"
        f"{draft.get('body', '')}\n"
    )
    return path


def draft_pending(limit: int = 25) -> dict:
    client = anthropic.Anthropic()
    conn = db.connect()
    pending = db.undrafted(conn, limit=limit)
    summary = {"drafted": 0, "errors": 0, "paths": []}
    for row in pending:
        d = draft_one(client, dict(row))
        now = datetime.now(timezone.utc).isoformat()
        db.mark_drafted(conn, row["id"], d.get("subject", ""), d.get("body", ""), now)
        path = _write_sample(dict(row), d)
        summary["drafted"] += 1
        summary["paths"].append(str(path))
        if "(parse error)" in d.get("subject", ""):
            summary["errors"] += 1
        print(f"  [{row['id']}] → {path.name}")
    return summary
