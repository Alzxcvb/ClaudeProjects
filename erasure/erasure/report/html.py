"""HTML evidence report.

Combines a DROP receipt (if any), baseline scan, and optional verify diff
into a single standalone HTML file. Screenshots are embedded by relative
path so the report stays portable when bundled with state/scans/artifacts/.

The output is designed as an evidence artifact: a CA resident can share
the HTML + screenshot folder as proof of good-faith DROP submission and
as a non-compliance complaint packet for CPPA.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPORTS_DIR = Path("state/reports")

_STATUS_COLORS = {
    "resolved": "#16a34a",
    "persistent": "#dc2626",
    "new": "#ea580c",
    "unchanged_absent": "#6b7280",
    "errored": "#a16207",
}


def _rel(from_file: Path, target: str) -> str:
    try:
        return os.path.relpath(target, start=from_file.parent)
    except ValueError:
        return target


def render_report(
    *,
    profile_name: str,
    scan_path: Path,
    drop_receipt_path: Optional[Path] = None,
    verify_path: Optional[Path] = None,
    out_path: Optional[Path] = None,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_path or (REPORTS_DIR / f"report_{stamp}.html")

    scan = json.loads(scan_path.read_text(encoding="utf-8"))
    receipt = json.loads(drop_receipt_path.read_text(encoding="utf-8")) if drop_receipt_path else None
    verify = json.loads(verify_path.read_text(encoding="utf-8")) if verify_path else None

    rows = []
    for r in scan["results"]:
        shot = _rel(out, r["screenshot_path"])
        match = "yes" if r["name_match"] else "no"
        err = f'<div class="err">{r["error"]}</div>' if r.get("error") else ""
        rows.append(
            f'<tr><td>{r["broker_name"]}</td>'
            f'<td><a href="{r["opt_out_url"]}">opt-out</a></td>'
            f'<td class="match-{match}">{match}</td>'
            f'<td>{", ".join(r["matched_variants"]) or "—"}</td>'
            f'<td><a href="{shot}">screenshot</a>{err}</td></tr>'
        )

    verify_block = ""
    if verify:
        v_rows = []
        for v in verify["verifications"]:
            color = _STATUS_COLORS.get(v["status"], "#333")
            v_rows.append(
                f'<tr><td>{v["broker_name"]}</td>'
                f'<td style="color:{color};font-weight:600">{v["status"]}</td>'
                f'<td>{"yes" if v["baseline_match"] else "no"}</td>'
                f'<td>{"yes" if v["verify_match"] else "no"}</td></tr>'
            )
        verify_block = f"""
        <section>
          <h2>Verification diff</h2>
          <p class="muted">Baseline scan <code>{verify["baseline_id"]}</code> vs verify scan <code>{verify["verify_id"]}</code>.</p>
          <div class="stats">
            <span class="stat resolved">{verify["resolved"]} resolved</span>
            <span class="stat persistent">{verify["persistent"]} persistent</span>
            <span class="stat new">{verify["new"]} new</span>
            <span class="stat errored">{verify["errored"]} errored</span>
          </div>
          <table><thead><tr><th>Broker</th><th>Status</th><th>Baseline match</th><th>Verify match</th></tr></thead>
          <tbody>{"".join(v_rows)}</tbody></table>
        </section>
        """

    drop_block = ""
    if receipt:
        drop_block = f"""
        <section>
          <h2>DROP submission</h2>
          <dl>
            <dt>Submission ID</dt><dd><code>{receipt.get("submission_id", "—")}</code></dd>
            <dt>Confirmation</dt><dd><code>{receipt.get("confirmation_code") or "—"}</code></dd>
            <dt>Status</dt><dd>{receipt.get("status", "—")}</dd>
            <dt>Submitted</dt><dd>{receipt.get("submitted_at", "—")}</dd>
            <dt>Portal</dt><dd><a href="{receipt.get("portal_url", "")}">{receipt.get("portal_url", "")}</a></dd>
          </dl>
        </section>
        """

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Erasure report — {profile_name}</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #111; }}
  h1 {{ margin-bottom: 0.25rem; }}
  .muted {{ color: #6b7280; font-size: 0.9rem; }}
  section {{ margin-top: 2rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 0.75rem; }}
  th, td {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #e5e7eb; font-size: 0.9rem; }}
  th {{ background: #f9fafb; }}
  .match-yes {{ color: #dc2626; font-weight: 600; }}
  .match-no {{ color: #16a34a; font-weight: 600; }}
  .err {{ color: #a16207; font-size: 0.8rem; }}
  dl {{ display: grid; grid-template-columns: 160px 1fr; gap: 0.25rem 1rem; }}
  dt {{ color: #6b7280; }}
  .stats {{ display: flex; gap: 1rem; margin: 0.75rem 0; flex-wrap: wrap; }}
  .stat {{ padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.85rem; font-weight: 600; }}
  .stat.resolved {{ background: #dcfce7; color: #14532d; }}
  .stat.persistent {{ background: #fee2e2; color: #7f1d1d; }}
  .stat.new {{ background: #ffedd5; color: #7c2d12; }}
  .stat.errored {{ background: #fef3c7; color: #713f12; }}
  code {{ background: #f3f4f6; padding: 0.1rem 0.35rem; border-radius: 4px; font-size: 0.85rem; }}
</style></head>
<body>
  <h1>Erasure evidence report</h1>
  <p class="muted">Profile: <strong>{profile_name}</strong> · Generated {stamp}</p>

  {drop_block}

  <section>
    <h2>Baseline scan</h2>
    <p class="muted">Scan <code>{scan["scan_id"]}</code> · {scan["broker_count"]} brokers · {scan["name_match_count"]} matches · {scan["error_count"]} errors</p>
    <table><thead><tr><th>Broker</th><th>Opt-out</th><th>Name match</th><th>Variants</th><th>Evidence</th></tr></thead>
    <tbody>{"".join(rows)}</tbody></table>
  </section>

  {verify_block}

  <section>
    <h2>How to use this report</h2>
    <ul>
      <li><strong>Pre-DROP baseline:</strong> Submit DROP at <a href="https://privacy.ca.gov/drop">privacy.ca.gov/drop</a>. Save the confirmation.</li>
      <li><strong>45 days later:</strong> Re-run <code>erasure scan</code> + <code>erasure verify</code> to check for persistent matches.</li>
      <li><strong>Non-compliance:</strong> Persistent matches after 90 days are grounds for a CPPA complaint at <a href="https://cppa.ca.gov">cppa.ca.gov</a> — attach this report.</li>
    </ul>
  </section>
</body></html>
"""
    out.write_text(html, encoding="utf-8")
    return out
