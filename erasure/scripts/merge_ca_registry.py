"""Merge the California CPPA Data Broker Registry into brokers.yaml.

Fetches CA registry rows by fuzzy-matching canonical name against the existing
Grauer-derived brokers.yaml. CA-only brokers (in the registry but not in Grauer)
are added with `source: ca_registry` so the per-broker module count grows
toward the 1000+ legally-registered universe rather than just the ~55 hand-curated.

Source: https://cppa.ca.gov/data_broker_registry/
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import yaml

DEFAULT_CSV = Path("erasure/data/ca_registry_2025.csv")
DEFAULT_YAML = Path("erasure/data/brokers.yaml")

COL_NAME = "Data broker name:"
COL_DBA = "Doing Business As (DBA), if applicable:"
COL_WEBSITE = "Data broker primary website:"
COL_EMAIL = "Data broker primary contact email address:"
COL_CCPA_URL = (
    "Data Broker's primary website that contains details on how consumers "
    "can exercise their CA Consumer Privacy Act rights, including how to "
    "delete their personal information: "
)
COL_FCRA = (
    "The data broker or any of its subsidiaries is regulated by the federal "
    "Fair Credit Reporting Act (FCRA):"
)
COL_GLBA = (
    "The data broker or any of its subsidiaries is regulated by the federal "
    "Gramm-Leach-Bliley Act (GLBA):"
)
COL_MINORS = "The data broker collects personal information of minors:"


def canonical(name: str) -> str:
    n = name.lower().strip()
    n = re.sub(r"[\.,'\u2019\u2018\"\u201c\u201d]", "", n)
    n = re.sub(r"\b(inc|llc|ltd|co|corp|corporation|company|holdings|group)\b", "", n)
    n = re.sub(r"[^a-z0-9]+", "", n)
    return n


def truthy(v):
    return (v or "").strip().lower() in {"yes", "true", "y", "1"}


def _norm_key(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def load_ca_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as f:
        next(f)  # skip the banner row above the real header
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            normalized = {_norm_key(k): v for k, v in r.items() if k}
            if (normalized.get(_norm_key(COL_NAME)) or "").strip():
                rows.append(normalized)
        return rows


def merge(yaml_path: Path, csv_path: Path) -> None:
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {"brokers": []}
    brokers = data.get("brokers", [])
    by_canon = {canonical(b["name"]): b for b in brokers}

    rows = load_ca_rows(csv_path)
    matched = 0
    added = 0

    nk = _norm_key
    for row in rows:
        name = (row.get(nk(COL_NAME)) or "").strip()
        if not name:
            continue
        dba = (row.get(nk(COL_DBA)) or "").strip()
        canon_keys = {canonical(name)}
        if dba:
            canon_keys.add(canonical(dba))

        target = None
        for k in canon_keys:
            if k in by_canon:
                target = by_canon[k]
                break

        ca_block = {
            "ca_registered": True,
            "ca_dba": dba or None,
            "ca_website": (row.get(nk(COL_WEBSITE)) or "").strip() or None,
            "ca_contact_email": (row.get(nk(COL_EMAIL)) or "").strip() or None,
            "ca_ccpa_rights_url": (row.get(nk(COL_CCPA_URL)) or "").strip() or None,
            "ca_fcra": truthy(row.get(nk(COL_FCRA))),
            "ca_glba": truthy(row.get(nk(COL_GLBA))),
            "ca_collects_minors": truthy(row.get(nk(COL_MINORS))),
        }

        if target:
            target.update(ca_block)
            matched += 1
        else:
            new_entry = {
                "name": name,
                "category": "CA-Registered (no Grauer entry)",
                "priority": "normal",
                "flags": "",
                "opt_out_url": ca_block["ca_ccpa_rights_url"],
                "contact_emails": [ca_block["ca_contact_email"]] if ca_block["ca_contact_email"] else [],
                "method": "form" if ca_block["ca_ccpa_rights_url"] else "email" if ca_block["ca_contact_email"] else "unknown",
                "requires_email_verify": False,
                "requires_account": False,
                "requires_id": False,
                "requires_phone": False,
                "paid": False,
                "notes": None,
                "source": "ca_registry",
                **ca_block,
            }
            brokers.append(new_entry)
            by_canon[canonical(name)] = new_entry
            added += 1

    data["brokers"] = brokers
    header = (
        "# Erasure broker dataset (Grauer + CA CPPA registry)\n"
        "# Grauer source: https://github.com/yaelwrites/Big-Ass-Data-Broker-Opt-Out-List (CC BY-NC-SA)\n"
        "# CA registry source: https://cppa.ca.gov/data_broker_registry/ (public record)\n"
        f"# Total entries: {len(brokers)}\n"
        f"# Last merge: matched {matched}, added {added} CA-only entries\n"
    )
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)
    yaml_path.write_text(header + "\n" + body, encoding="utf-8")
    print(
        f"Merged: {matched} Grauer entries enriched with CA data, "
        f"{added} CA-only entries added. Total: {len(brokers)}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yaml", default=str(DEFAULT_YAML), type=Path)
    ap.add_argument("--csv", default=str(DEFAULT_CSV), type=Path)
    args = ap.parse_args()
    merge(args.yaml, args.csv)


if __name__ == "__main__":
    main()
