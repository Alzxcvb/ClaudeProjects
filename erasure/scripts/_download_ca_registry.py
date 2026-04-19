"""One-shot download of the CA CPPA registry CSV."""
import sys
from pathlib import Path
import httpx

URL = "https://cppa.ca.gov/data_broker_registry/registry.csv"
OUT = Path(__file__).resolve().parent.parent / "erasure" / "data" / "ca_registry.csv"

OUT.parent.mkdir(parents=True, exist_ok=True)
r = httpx.get(URL, follow_redirects=True, timeout=30)
r.raise_for_status()
OUT.write_bytes(r.content)
print(f"Saved {len(r.content):,} bytes → {OUT}")
lines = OUT.read_text(encoding="utf-8-sig").splitlines()
print(f"  Header: {lines[0]}")
print(f"  Rows:   {len(lines) - 1}")
