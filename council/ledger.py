"""SQLite track-record ledger for council.

Schema per plan-council.md §4, plus the C1 snapshot columns
(rec_a_wins/rec_a_resolved/rec_b_wins/rec_b_resolved) recorded at insert
time so the "did the judge follow the better record" stat never depends on
current ledger state (see C1).
"""
from __future__ import annotations

import datetime
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Union

PathLike = Union[str, Path]

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    question TEXT NOT NULL,
    persona_a TEXT NOT NULL,
    persona_b TEXT NOT NULL,
    provider_a TEXT NOT NULL,
    provider_b TEXT NOT NULL,
    judge_provider TEXT NOT NULL,
    case_a TEXT NOT NULL,
    case_b TEXT NOT NULL,
    rebuttal_a TEXT NOT NULL,
    rebuttal_b TEXT NOT NULL,
    position1_side TEXT NOT NULL,
    winner TEXT NOT NULL,
    confidence REAL NOT NULL,
    key_reason TEXT NOT NULL,
    would_change_mind TEXT NOT NULL,
    judge_raw TEXT NOT NULL,
    outcome TEXT,
    resolved_at TEXT,
    rec_a_wins INTEGER NOT NULL,
    rec_a_resolved INTEGER NOT NULL,
    rec_b_wins INTEGER NOT NULL,
    rec_b_resolved INTEGER NOT NULL
);
"""

_VALID_OUTCOMES = ("A", "B", "neither")


class LedgerError(Exception):
    """Raised for a bad question id or a bad outcome value."""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _connect(path: PathLike) -> sqlite3.Connection:
    # A4: timeout=10, WAL journal mode, 10s busy timeout, so concurrent
    # ask/resolve/history calls don't collide.
    conn = sqlite3.connect(str(path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA_SQL)
    conn.commit()


def insert(
    path: PathLike,
    *,
    question: str,
    persona_a: str,
    persona_b: str,
    provider_a: str,
    provider_b: str,
    judge_provider: str,
    case_a: str,
    case_b: str,
    rebuttal_a: str,
    rebuttal_b: str,
    position1_side: str,
    winner: str,
    confidence: float,
    key_reason: str,
    would_change_mind: str,
    judge_raw: str,
    rec_a_wins: int,
    rec_a_resolved: int,
    rec_b_wins: int,
    rec_b_resolved: int,
) -> int:
    """Insert one judged row. The four rec_* snapshot values are required
    (no defaults): they must be the exact record numbers shown to the judge
    (C1), and omitting one is a caller bug, not a soft default."""
    conn = _connect(path)
    try:
        _ensure_schema(conn)
        cur = conn.execute(
            """
            INSERT INTO questions (
                created_at, question, persona_a, persona_b, provider_a, provider_b,
                judge_provider, case_a, case_b, rebuttal_a, rebuttal_b,
                position1_side, winner, confidence, key_reason, would_change_mind,
                judge_raw, outcome, resolved_at,
                rec_a_wins, rec_a_resolved, rec_b_wins, rec_b_resolved
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)
            """,
            (
                _now(), question, persona_a, persona_b, provider_a, provider_b,
                judge_provider, case_a, case_b, rebuttal_a, rebuttal_b,
                position1_side, winner, confidence, key_reason, would_change_mind,
                judge_raw,
                rec_a_wins, rec_a_resolved, rec_b_wins, rec_b_resolved,
            ),
        )
        conn.commit()
        assert cur.lastrowid is not None
        return cur.lastrowid
    finally:
        conn.close()


def count(path: PathLike) -> int:
    conn = _connect(path)
    try:
        _ensure_schema(conn)
        row = conn.execute("SELECT COUNT(*) FROM questions").fetchone()
        return row[0]
    finally:
        conn.close()


def resolve(path: PathLike, question_id: int, outcome: str) -> Optional[str]:
    """Set outcome + resolved_at for a row. Overwrites silently, returning
    the previous outcome (may be None). Raises LedgerError on an unknown id
    or a value outside A/B/neither."""
    if outcome not in _VALID_OUTCOMES:
        raise LedgerError(
            f"invalid outcome {outcome!r}: must be one of {_VALID_OUTCOMES}"
        )
    conn = _connect(path)
    try:
        _ensure_schema(conn)
        row = conn.execute(
            "SELECT outcome FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
        if row is None:
            raise LedgerError(f"no question with id {question_id}")
        previous = row["outcome"]
        conn.execute(
            "UPDATE questions SET outcome = ?, resolved_at = ? WHERE id = ?",
            (outcome, _now(), question_id),
        )
        conn.commit()
        return previous
    finally:
        conn.close()


def _record_rows(conn: sqlite3.Connection, persona: str) -> Dict[str, Optional[float]]:
    rows = conn.execute(
        "SELECT persona_a, persona_b, outcome FROM questions "
        "WHERE (persona_a = ? OR persona_b = ?) AND outcome IN ('A','B')",
        (persona, persona),
    ).fetchall()
    wins = 0
    resolved = 0
    for row in rows:
        resolved += 1
        side = "A" if row["persona_a"] == persona else "B"
        if row["outcome"] == side:
            wins += 1
    rate = (wins / resolved) if resolved else None
    return {"wins": wins, "resolved": resolved, "rate": rate}


def record(path: PathLike, persona: str) -> Dict[str, Optional[float]]:
    """Persona P's record: rows with outcome in (A,B) where P sat on either
    side; win if P's side == outcome. 'neither' rows and unresolved rows
    (B3) are excluded, so `resolved` here can be 0 (rate=None, no division)."""
    conn = _connect(path)
    try:
        _ensure_schema(conn)
        return _record_rows(conn, persona)
    finally:
        conn.close()


def history(path: PathLike) -> dict:
    """Return read-only stats for `/council history`. Formatting text lives
    in __main__.py; this returns plain data."""
    conn = _connect(path)
    try:
        _ensure_schema(conn)

        total_rows = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        resolved_total = conn.execute(
            "SELECT COUNT(*) FROM questions WHERE outcome IN ('A','B','neither')"
        ).fetchone()[0]

        persona_names = set()
        for row in conn.execute("SELECT DISTINCT persona_a FROM questions"):
            persona_names.add(row[0])
        for row in conn.execute("SELECT DISTINCT persona_b FROM questions"):
            persona_names.add(row[0])

        personas = {name: _record_rows(conn, name) for name in sorted(persona_names)}

        judged_rows = conn.execute(
            "SELECT provider_a, provider_b, judge_provider, winner, confidence, outcome, "
            "rec_a_wins, rec_a_resolved, rec_b_wins, rec_b_resolved "
            "FROM questions"
        ).fetchall()

        correct = 0
        scored = 0
        brier_sum = 0.0
        brier_n = 0
        same_side_matches = 0
        same_side_total = 0
        better_matches = 0
        better_total = 0

        for row in judged_rows:
            # A1: judge_same_side is computed at read time, not stored.
            same_side_total += 1
            judge_side = "A" if row["provider_a"] == row["judge_provider"] else "B"
            if row["winner"] == judge_side:
                same_side_matches += 1

            # C1: "followed better record" uses ONLY the snapshot columns
            # captured at insert time, regardless of the row's own outcome
            # or any resolve() that happened later.
            ra_resolved = row["rec_a_resolved"]
            rb_resolved = row["rec_b_resolved"]
            if ra_resolved >= 1 and rb_resolved >= 1:
                rate_a = row["rec_a_wins"] / ra_resolved
                rate_b = row["rec_b_wins"] / rb_resolved
                if rate_a != rate_b:
                    better_total += 1
                    better_side = "A" if rate_a > rate_b else "B"
                    if row["winner"] == better_side:
                        better_matches += 1

            # B3: 'neither' rows are excluded from judge accuracy and Brier.
            outcome = row["outcome"]
            if outcome in ("A", "B"):
                scored += 1
                if row["winner"] == outcome:
                    correct += 1
                p = row["confidence"] if row["winner"] == "A" else (1 - row["confidence"])
                y = 1.0 if outcome == "A" else 0.0
                brier_sum += (p - y) ** 2
                brier_n += 1

        judge_accuracy = (correct / scored) if scored else None
        brier = (brier_sum / brier_n) if brier_n else None

        last_rows_raw = conn.execute(
            "SELECT * FROM questions ORDER BY id DESC LIMIT 10"
        ).fetchall()
        last_rows: List[dict] = [dict(r) for r in last_rows_raw]

        return {
            "total_rows": total_rows,
            "resolved_total": resolved_total,
            "personas": personas,
            "judge": {
                "accuracy": judge_accuracy,
                "accuracy_n": scored,
                "brier": brier,
                "brier_n": brier_n,
                "same_side_matches": same_side_matches,
                "same_side_total": same_side_total,
            },
            "better_record_followed": {
                "matches": better_matches,
                "total": better_total,
            },
            "last_rows": last_rows,
        }
    finally:
        conn.close()
