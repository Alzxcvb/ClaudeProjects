#!/usr/bin/env python3
"""Predict how a LinkedIn post variant will perform.

Outputs comparative score + numeric forecast (side-by-side), with explicit
LOW-N caveat until n_labeled >= 10.

Usage:
    python predict.py --body "post body here"
    python predict.py --body-file path/to/variant.txt
    python predict.py --json '{"body": "...", "hook_archetype": "...", "word_count": 120}'
    python predict.py --body "..." --dry-run    # show the prompt, skip the API

History comes from the content database (content.db, see ./crm).
"""
import argparse
import json
import re
import statistics
import sys
from pathlib import Path

from anthropic import Anthropic

ROOT = Path(__file__).parent
PROMPT_PATH = ROOT / "prompts" / "predictor.md"

MODEL = "claude-haiku-4-5-20251001"


def load_posts():
    from contentcrm.fewshot import load_posts_compat

    return load_posts_compat(require_body=False)


def format_history(posts, limit=10):
    labeled = [p for p in posts if p.get("actuals")]
    recent = labeled[-limit:]
    if not recent:
        return "(no labeled posts yet)", 0, None
    lines = [
        f"- {p['id']}: format={p['format']}, hook={p['hook_archetype']}, "
        f"words={p['word_count']} → impressions={p['actuals']['impressions']}, "
        f"reactions={p['actuals']['reactions']}, comments={p['actuals']['comments']}"
        for p in recent
    ]
    median_imp = statistics.median(p["actuals"]["impressions"] for p in recent)
    header = f"Median impressions across labeled history (n={len(recent)}): {median_imp:.0f}"
    return header + "\n" + "\n".join(lines), len(labeled), median_imp


def extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--body", help="Post body text")
    g.add_argument("--body-file", help="Path to file with post body")
    g.add_argument("--json", dest="json_in", help="Full variant JSON")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the assembled prompt and exit without calling the API",
    )
    args = ap.parse_args()

    if args.body:
        variant = {"body": args.body}
    elif args.body_file:
        variant = {"body": Path(args.body_file).read_text()}
    else:
        variant = json.loads(args.json_in)

    posts = load_posts()
    history, n_labeled, median_imp = format_history(posts)

    system = PROMPT_PATH.read_text()
    user = f"""VARIANT TO EVALUATE:
{json.dumps(variant, indent=2, ensure_ascii=False)}

LABELED HISTORY (n_labeled={n_labeled}):

{history}

Output strict JSON only.
"""

    if args.dry_run:
        print(f"--- system ({PROMPT_PATH}) ---\n{system}\n--- user ---\n{user}")
        return

    client = Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = resp.content[0].text
    payload = extract_json(raw)

    try:
        forecast = json.loads(payload)
    except json.JSONDecodeError as e:
        print(f"[predict] model returned non-JSON: {e}", file=sys.stderr)
        print(raw, file=sys.stderr)
        sys.exit(1)

    print(json.dumps(forecast, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
