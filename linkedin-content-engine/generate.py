#!/usr/bin/env python3
"""Generate 3 LinkedIn post variants from a topic + optional notes.

Each call pulls the last 10 published posts from the content database
(content.db, see ./crm) as few-shot examples, so the prompt evolves as the
history grows.

Usage:
    python generate.py "your topic here"
    python generate.py "topic" --notes "raw observations to weave in"
    python generate.py "topic" --axis length        # vary length instead of hook
    python generate.py "topic" --axis cta_type      # vary CTA instead of hook
    python generate.py "topic" --dry-run            # show the prompt, skip the API
"""
import argparse
import json
import re
import sys
from pathlib import Path

from anthropic import Anthropic

ROOT = Path(__file__).parent
PROMPT_PATH = ROOT / "prompts" / "generator.md"

MODEL = "claude-sonnet-4-6"


def load_posts():
    # Bodiless runs (a few legacy ones) are excluded: an example with no text
    # can't teach voice. predict.py still sees them, it only needs metrics.
    from contentcrm.fewshot import load_posts_compat

    return load_posts_compat(require_body=True)


def format_examples(posts, limit=10):
    recent = posts[-limit:]
    if not recent:
        return "(no prior posts — generate based on style rules only)"
    blocks = []
    for p in recent:
        actuals = p.get("actuals")
        metrics = (
            f"impressions={actuals['impressions']}, "
            f"reactions={actuals['reactions']}, "
            f"comments={actuals['comments']}"
            if actuals
            else "not yet logged"
        )
        blocks.append(
            f"### {p['id']}  (format={p['format']}, hook={p['hook_archetype']}, words={p['word_count']})\n"
            f"**Actuals:** {metrics}\n"
            f"**Body:**\n{p['body']}\n"
            f"**Notes:** {p.get('notes', '')}"
        )
    return "\n\n---\n\n".join(blocks)


def extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topic", help="Topic for the post")
    ap.add_argument("--notes", default="", help="Optional raw notes / observations")
    ap.add_argument(
        "--axis",
        default="hook_archetype",
        choices=["hook_archetype", "length", "cta_type"],
        help="Which axis to vary across the 3 variants",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the assembled prompt and exit without calling the API",
    )
    args = ap.parse_args()

    posts = load_posts()
    examples = format_examples(posts)

    system = PROMPT_PATH.read_text()
    user = f"""TOPIC: {args.topic}

NOTES (optional context): {args.notes or "(none)"}

VARY ON THIS AXIS: {args.axis}

LAST {min(len(posts), 10)} POSTS (your few-shot, n_total={len(posts)}):

{examples}

Generate 3 variants. Output strict JSON only.
"""

    if args.dry_run:
        print(f"--- system ({PROMPT_PATH}) ---\n{system}\n--- user ---\n{user}")
        return

    client = Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = resp.content[0].text
    payload = extract_json(raw)

    try:
        variants = json.loads(payload)
    except json.JSONDecodeError as e:
        print(f"[generate] model returned non-JSON: {e}", file=sys.stderr)
        print(raw, file=sys.stderr)
        sys.exit(1)

    print(json.dumps(variants, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
