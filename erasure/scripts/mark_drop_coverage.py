"""Mark every ca_registered broker in brokers.yaml with coverage: drop.

Per-broker modules use this flag to skip CA-registered brokers for CA users
whose DROP submission has been acknowledged — DROP fans out to them already.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

DEFAULT_YAML = Path("erasure/data/brokers.yaml")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yaml", default=str(DEFAULT_YAML), type=Path)
    args = ap.parse_args()

    raw = args.yaml.read_text(encoding="utf-8")
    header_lines: list[str] = []
    body_start = 0
    for i, line in enumerate(raw.splitlines()):
        if line.startswith("#") or not line.strip():
            header_lines.append(line)
            body_start = i + 1
            continue
        break
    body = "\n".join(raw.splitlines()[body_start:])
    data = yaml.safe_load(body) or {"brokers": []}

    marked = 0
    for b in data.get("brokers", []):
        if b.get("ca_registered"):
            if b.get("coverage") != "drop":
                b["coverage"] = "drop"
                marked += 1

    new_body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)
    args.yaml.write_text("\n".join(header_lines) + "\n" + new_body, encoding="utf-8")
    print(f"Marked {marked} brokers with coverage: drop")


if __name__ == "__main__":
    main()
