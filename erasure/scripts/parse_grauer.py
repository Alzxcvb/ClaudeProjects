"""Parse the BADBOOL (Yael Grauer) markdown into structured YAML.

Source: https://github.com/yaelwrites/Big-Ass-Data-Broker-Opt-Out-List
Source license: CC BY-NC-SA. Derived YAML inherits the same license — keep
attribution intact in the output file header.

Usage:
    python scripts/parse_grauer.py [--src .cache/grauer/README.md] [--out erasure/data/brokers.yaml]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Optional

import yaml

# Priority emojis from the Grauer key
PRIORITY_CRUCIAL = "💐"
PRIORITY_HIGH = "☠"
REQ_ID = "🎫"
REQ_PHONE = "📞"
REQ_PAYMENT = "💰"

LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
EMAIL_RE = re.compile(r"<([^@\s>]+@[^>\s]+)>|\b([\w.+-]+@[\w-]+\.[\w.-]+)\b")
SECTION_RE = re.compile(r"^### (.+)$")
H2_RE = re.compile(r"^## (.+)$")

# Heuristic: anchor-text keywords that mark a link as an opt-out URL
OPT_OUT_KEYWORDS = (
    "opt out",
    "opt-out",
    "remove",
    "removal",
    "delete",
    "suppress",
    "privacy request",
    "do not sell",
    "right to know",
    "request form",
    "data request",
)


def parse_priority(header_emojis: str) -> str:
    if PRIORITY_CRUCIAL in header_emojis:
        return "crucial"
    if PRIORITY_HIGH in header_emojis:
        return "high"
    return "normal"


def split_header(header: str) -> tuple[str, str]:
    """Split '### 💐 📞 White Pages' → ('💐 📞', 'White Pages')."""
    parts = header.split()
    name_start = 0
    for i, p in enumerate(parts):
        if any(c.isalnum() for c in p):
            name_start = i
            break
    return " ".join(parts[:name_start]), " ".join(parts[name_start:]).strip()


def classify_method(body: str, opt_out_url: Optional[str], emails: list[str]) -> str:
    body_lower = body.lower()
    if "mail in" in body_lower or "fax" in body_lower or "notarized" in body_lower:
        return "mail"
    if opt_out_url:
        return "form"
    if emails:
        return "email"
    return "unknown"


def find_opt_out_url(links: list[tuple[str, str]]) -> Optional[str]:
    for text, url in links:
        text_l = text.lower()
        if any(k in text_l for k in OPT_OUT_KEYWORDS):
            return url
    return None


def parse(src: Path) -> list[dict]:
    text = src.read_text(encoding="utf-8")
    lines = text.splitlines()

    brokers: list[dict] = []
    current_h2: Optional[str] = None
    current: Optional[dict] = None
    body_lines: list[str] = []

    def flush():
        if not current:
            return
        body = "\n".join(body_lines).strip()
        links = LINK_RE.findall(body)
        emails_raw = EMAIL_RE.findall(body)
        emails = [a or b for (a, b) in emails_raw if (a or b)]
        opt_out_url = find_opt_out_url(links)
        method = classify_method(body, opt_out_url, emails)
        current["opt_out_url"] = opt_out_url
        current["contact_emails"] = list(dict.fromkeys(emails))
        current["method"] = method
        current["requires_email_verify"] = (
            "verify" in body.lower() and "email" in body.lower()
        ) or "click on a link sent to you via email" in body.lower()
        current["requires_account"] = (
            "sign up" in body.lower()
            or "create an account" in body.lower()
            or "free account" in body.lower()
        )
        current["requires_id"] = REQ_ID in current.get("flags", "") or "driver" in body.lower() and "license" in body.lower()
        current["requires_phone"] = REQ_PHONE in current.get("flags", "")
        current["paid"] = REQ_PAYMENT in current.get("flags", "")
        # Compress notes to first ~400 chars to keep YAML readable
        current["notes"] = body[:400].strip() if body else None
        brokers.append(current)

    for line in lines:
        h2 = H2_RE.match(line)
        sec = SECTION_RE.match(line)
        if h2:
            flush()
            current = None
            body_lines = []
            current_h2 = h2.group(1).strip()
            continue
        if sec:
            flush()
            flags, name = split_header(sec.group(1))
            current = {
                "name": name,
                "category": current_h2 or "Uncategorized",
                "priority": parse_priority(flags),
                "flags": flags,
            }
            body_lines = []
            continue
        if current is not None:
            body_lines.append(line)

    flush()
    return brokers


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=".cache/grauer/README.md", type=Path)
    ap.add_argument("--out", default="erasure/data/brokers.yaml", type=Path)
    args = ap.parse_args()

    brokers = parse(args.src)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    header = (
        "# Erasure broker dataset\n"
        "#\n"
        "# Derived from Yael Grauer's Big Ass Data Broker Opt-Out List (BADBOOL)\n"
        "# Source: https://github.com/yaelwrites/Big-Ass-Data-Broker-Opt-Out-List\n"
        "# License of source: CC BY-NC-SA 4.0 — derived data inherits this license.\n"
        "# Do not redistribute commercially without re-deriving from primary sources.\n"
        "#\n"
        f"# Auto-generated by scripts/parse_grauer.py from BADBOOL @ {args.src}.\n"
        f"# Total entries: {len(brokers)}\n"
    )
    body = yaml.safe_dump(
        {"brokers": brokers},
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
    args.out.write_text(header + "\n" + body, encoding="utf-8")
    print(f"Wrote {len(brokers)} brokers → {args.out}")
    by_pri = {}
    for b in brokers:
        by_pri[b["priority"]] = by_pri.get(b["priority"], 0) + 1
    print(f"By priority: {by_pri}")


if __name__ == "__main__":
    main()
