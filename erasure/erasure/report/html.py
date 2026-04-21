"""HTML evidence report.

Combines a DROP receipt (if any), baseline scan, and optional verify diff
into a single standalone HTML file. Screenshots are embedded by relative
path so the report stays portable when bundled with state/scans/artifacts/.

The output is designed as an evidence artifact: a CA resident can share
the HTML + screenshot folder as proof of good-faith DROP submission and
as a non-compliance complaint packet for CPPA.
"""

from __future__ import annotations

import html as _html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPORTS_DIR = Path("state/reports")

# erasure/erasure/report/html.py → repo root "erasure/"
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DASHBOARD_TEMPLATE = _REPO_ROOT / "dashboard" / "index.html"
_EVIDENCE_MARKER = "<!-- ERASURE_EVIDENCE_MARKER -->"

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


def _latest(dir_path: Path, glob: str) -> Optional[Path]:
    if not dir_path.exists():
        return None
    candidates = list(dir_path.glob(glob))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def latest_scan_path() -> Optional[Path]:
    from erasure.brokers.scan import SCANS_DIR
    return _latest(SCANS_DIR, "scan_*.json")


def latest_receipt_path() -> Optional[Path]:
    from erasure.drop.client import RECEIPTS_DIR
    return _latest(RECEIPTS_DIR, "drop_*.json")


def latest_verify_path() -> Optional[Path]:
    from erasure.verify.diff import VERIFY_DIR
    return _latest(VERIFY_DIR, "verify_*.json")


def latest_accounts_path() -> Optional[Path]:
    from erasure.accounts.sherlock import ACCOUNTS_DIR
    return _latest(ACCOUNTS_DIR, "accounts_*.json")


def _render_evidence_block(
    *,
    profile_name: str,
    scan: dict,
    scan_rel_dir: Path,
    receipt: Optional[dict],
    verify: Optional[dict],
    accounts: Optional[dict],
    stamp: str,
) -> str:
    """Build the dark-themed evidence block injected into the dashboard template."""
    esc = _html.escape

    # Scan rows (cap at 25 in the dashboard for readability — full list is in the standalone report)
    scan_rows = []
    for r in scan["results"][:25]:
        shot_rel = os.path.relpath(r["screenshot_path"], start=scan_rel_dir) if r.get("screenshot_path") else ""
        match_class = "match-yes" if r["name_match"] else "match-no"
        match_text = "yes" if r["name_match"] else "no"
        variants = ", ".join(r.get("matched_variants") or []) or "—"
        screenshot_cell = (
            f'<a href="{esc(shot_rel)}" target="_blank">screenshot</a>' if shot_rel else "—"
        )
        scan_rows.append(
            f"<tr>"
            f"<td>{esc(r['broker_name'])}</td>"
            f'<td><a href="{esc(r["opt_out_url"])}" target="_blank" rel="noopener">opt-out</a></td>'
            f'<td class="{match_class}">{match_text}</td>'
            f"<td>{esc(variants)}</td>"
            f"<td>{screenshot_cell}</td>"
            f"</tr>"
        )
    truncated_note = ""
    if len(scan["results"]) > 25:
        truncated_note = (
            f'<p class="ev-muted">Showing top 25 of {len(scan["results"])}. '
            f"Full list in the standalone evidence report.</p>"
        )

    drop_card = ""
    if receipt:
        drop_card = f"""
        <div class="ev-card">
          <h3>DROP submission</h3>
          <dl class="ev-dl">
            <dt>ID</dt><dd><code>{esc(str(receipt.get("submission_id", "—")))}</code></dd>
            <dt>Confirmation</dt><dd><code>{esc(str(receipt.get("confirmation_code") or "—"))}</code></dd>
            <dt>Status</dt><dd><span class="ev-pill ev-pill-{esc(str(receipt.get("status", "pending")))}">{esc(str(receipt.get("status", "—")))}</span></dd>
            <dt>Submitted</dt><dd>{esc(str(receipt.get("submitted_at", "—")))}</dd>
            <dt>Portal</dt><dd><a href="{esc(str(receipt.get("portal_url", "")))}" target="_blank" rel="noopener">{esc(str(receipt.get("portal_url", "")))}</a></dd>
          </dl>
        </div>
        """

    accounts_card = ""
    accounts_details = ""
    if accounts:
        account_hits = accounts.get("hits", [])
        hit_rows = []
        for h in account_hits[:50]:
            hit_rows.append(
                f"<tr>"
                f"<td>{esc(h['site'])}</td>"
                f'<td><a href="{esc(h["url"])}" target="_blank" rel="noopener">{esc(h["url"])}</a></td>'
                f"</tr>"
            )
        acct_truncated = ""
        if len(account_hits) > 50:
            acct_truncated = f'<p class="ev-muted">Showing top 50 of {len(account_hits)}.</p>'
        accounts_card = f"""
        <div class="ev-card">
          <h3>Account exposure (Sherlock)</h3>
          <p class="ev-muted">Username <code>{esc(accounts.get("username", "—"))}</code></p>
          <div class="ev-stats">
            <span class="ev-stat ev-persistent">{accounts.get("found_count", 0)} accounts found</span>
          </div>
        </div>
        """
        if account_hits:
            accounts_details = f"""
    <details class="ev-details">
        <summary>Sherlock hits ({len(account_hits)})</summary>
        <table class="ev-table">
            <thead><tr><th>Site</th><th>URL</th></tr></thead>
            <tbody>{''.join(hit_rows)}</tbody>
        </table>
        {acct_truncated}
    </details>
"""

    verify_card = ""
    if verify:
        verify_card = f"""
        <div class="ev-card">
          <h3>Verification diff</h3>
          <p class="ev-muted">Baseline <code>{esc(verify["baseline_id"])}</code> vs verify <code>{esc(verify["verify_id"])}</code>.</p>
          <div class="ev-stats">
            <span class="ev-stat ev-resolved">{verify["resolved"]} resolved</span>
            <span class="ev-stat ev-persistent">{verify["persistent"]} persistent</span>
            <span class="ev-stat ev-new">{verify["new"]} new</span>
            <span class="ev-stat ev-errored">{verify["errored"]} errored</span>
          </div>
        </div>
        """

    return f"""
<div class="evidence">
    <div class="evidence-header">
        <h2>Your live Erasure evidence</h2>
        <p class="ev-muted">Profile <strong>{esc(profile_name)}</strong> · rendered {esc(stamp)}</p>
    </div>

    <div class="ev-cards">
        <div class="ev-card">
            <h3>Latest broker scan</h3>
            <p class="ev-muted">Scan <code>{esc(scan["scan_id"])}</code></p>
            <div class="ev-stats">
                <span class="ev-stat">{scan["broker_count"]} brokers</span>
                <span class="ev-stat ev-persistent">{scan["name_match_count"]} matches</span>
                <span class="ev-stat ev-errored">{scan["error_count"]} errors</span>
            </div>
        </div>
        {drop_card}
        {verify_card}
        {accounts_card}
    </div>

    <details class="ev-details" open>
        <summary>Per-broker results</summary>
        <table class="ev-table">
            <thead><tr><th>Broker</th><th>Opt-out</th><th>Match</th><th>Variants</th><th>Evidence</th></tr></thead>
            <tbody>{''.join(scan_rows)}</tbody>
        </table>
        {truncated_note}
    </details>
    {accounts_details}
</div>

<style>
.evidence {{ max-width: 960px; margin: 0 auto 2rem; padding: 0 1rem; }}
.evidence-header h2 {{ font-size: 1.1rem; text-transform: uppercase; letter-spacing: 0.05em; color: #8b949e; margin-bottom: 0.25rem; }}
.ev-muted {{ color: #8b949e; font-size: 0.82rem; margin-top: 0.25rem; }}
.ev-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 0.8rem; margin-top: 1rem; }}
.ev-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 1rem 1.2rem; }}
.ev-card h3 {{ font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.05em; color: #8b949e; margin-bottom: 0.5rem; }}
.ev-dl {{ display: grid; grid-template-columns: 110px 1fr; gap: 0.25rem 0.8rem; font-size: 0.88rem; }}
.ev-dl dt {{ color: #8b949e; }}
.ev-dl dd {{ color: #e6edf3; word-break: break-word; }}
.ev-stats {{ display: flex; gap: 0.4rem; flex-wrap: wrap; margin-top: 0.4rem; }}
.ev-stat {{ padding: 0.2rem 0.55rem; border-radius: 999px; font-size: 0.78rem; font-weight: 600; background: #0d1117; border: 1px solid #30363d; color: #e6edf3; }}
.ev-stat.ev-resolved   {{ border-color: #238636; color: #3fb950; }}
.ev-stat.ev-persistent {{ border-color: #da3633; color: #f85149; }}
.ev-stat.ev-new        {{ border-color: #bd561d; color: #f0883e; }}
.ev-stat.ev-errored    {{ border-color: #9e6a03; color: #e3b341; }}
.ev-pill {{ padding: 0.15rem 0.5rem; border-radius: 6px; font-size: 0.78rem; font-weight: 600; background: #0d1117; border: 1px solid #30363d; }}
.ev-pill-confirmed {{ border-color: #238636; color: #3fb950; }}
.ev-pill-submitted {{ border-color: #1f6feb; color: #58a6ff; }}
.ev-pill-pending   {{ border-color: #9e6a03; color: #e3b341; }}
.ev-details {{ margin-top: 1rem; background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 0.8rem 1.2rem; }}
.ev-details summary {{ cursor: pointer; color: #8b949e; text-transform: uppercase; font-size: 0.78rem; letter-spacing: 0.05em; }}
.ev-table {{ width: 100%; border-collapse: collapse; margin-top: 0.8rem; font-size: 0.85rem; }}
.ev-table th, .ev-table td {{ text-align: left; padding: 0.45rem 0.55rem; border-bottom: 1px solid #21262d; }}
.ev-table th {{ color: #8b949e; font-weight: 600; }}
.ev-table a {{ color: #58a6ff; text-decoration: none; }}
.ev-table a:hover {{ text-decoration: underline; }}
.ev-table .match-yes {{ color: #f85149; font-weight: 600; }}
.ev-table .match-no  {{ color: #3fb950; font-weight: 600; }}
</style>
"""


def render_dashboard(
    *,
    profile_name: str,
    scan_path: Path,
    drop_receipt_path: Optional[Path] = None,
    verify_path: Optional[Path] = None,
    accounts_path: Optional[Path] = None,
    out_path: Optional[Path] = None,
    template_path: Optional[Path] = None,
) -> Path:
    """Render the Cyber Hygiene Dashboard with live Erasure evidence injected.

    Reads the static dashboard template, replaces the ERASURE_EVIDENCE_MARKER
    with a populated evidence block, and writes a new standalone HTML file.
    The template itself is never modified — re-running is idempotent.
    """
    template = template_path or DASHBOARD_TEMPLATE
    if not template.exists():
        raise FileNotFoundError(f"Dashboard template not found at {template}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_path or (REPORTS_DIR / f"dashboard_{stamp}.html")

    scan = json.loads(scan_path.read_text(encoding="utf-8"))
    receipt = json.loads(drop_receipt_path.read_text(encoding="utf-8")) if drop_receipt_path else None
    verify = json.loads(verify_path.read_text(encoding="utf-8")) if verify_path else None
    accounts = json.loads(accounts_path.read_text(encoding="utf-8")) if accounts_path else None

    evidence_html = _render_evidence_block(
        profile_name=profile_name,
        scan=scan,
        scan_rel_dir=out.parent,
        receipt=receipt,
        verify=verify,
        accounts=accounts,
        stamp=stamp,
    )

    template_html = template.read_text(encoding="utf-8")
    if _EVIDENCE_MARKER not in template_html:
        raise ValueError(f"Template at {template} is missing {_EVIDENCE_MARKER}")
    populated = template_html.replace(_EVIDENCE_MARKER, evidence_html, 1)
    out.write_text(populated, encoding="utf-8")
    return out
