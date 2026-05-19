"""SQLite store for the outreach POC."""
import json
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "state" / "db.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT    NOT NULL,           -- "reddit"
    handle          TEXT    NOT NULL,           -- reddit username
    post_url        TEXT    NOT NULL UNIQUE,    -- dedup key
    subreddit       TEXT,
    post_title      TEXT,
    post_body       TEXT,
    matched_keyword TEXT,
    captured_at     TEXT    NOT NULL,           -- iso
    classified_at   TEXT,
    relevance       INTEGER,                    -- 0-10
    persona         TEXT,                       -- "finance" | "broad" | NULL
    filter_reason   TEXT,                       -- only set if dropped
    drafted_at      TEXT,
    draft_subject   TEXT,
    draft_body      TEXT,
    email           TEXT,                       -- filled later via enricher
    sent_at         TEXT
);

CREATE INDEX IF NOT EXISTS idx_prospects_classified ON prospects(classified_at);
CREATE INDEX IF NOT EXISTS idx_prospects_drafted    ON prospects(drafted_at);
CREATE INDEX IF NOT EXISTS idx_prospects_relevance  ON prospects(relevance);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def insert_prospect(conn: sqlite3.Connection, row: dict) -> Optional[int]:
    """Insert; silently ignore dupes (post_url is UNIQUE)."""
    try:
        cur = conn.execute(
            """INSERT INTO prospects
               (source, handle, post_url, subreddit, post_title, post_body,
                matched_keyword, captured_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["source"], row["handle"], row["post_url"], row.get("subreddit"),
                row.get("post_title"), row.get("post_body"), row.get("matched_keyword"),
                row["captured_at"],
            ),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def unclassified(conn: sqlite3.Connection, limit: int = 50) -> Iterable[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM prospects WHERE classified_at IS NULL LIMIT ?", (limit,)
    ).fetchall()


def undrafted(conn: sqlite3.Connection, limit: int = 50) -> Iterable[sqlite3.Row]:
    return conn.execute(
        """SELECT * FROM prospects
           WHERE drafted_at IS NULL
             AND classified_at IS NOT NULL
             AND filter_reason IS NULL
             AND relevance >= 3
           ORDER BY relevance DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()


def mark_classified(
    conn: sqlite3.Connection, prospect_id: int,
    relevance: int, persona: Optional[str], filter_reason: Optional[str],
    when: str,
) -> None:
    conn.execute(
        """UPDATE prospects
              SET classified_at = ?, relevance = ?,
                  persona = ?, filter_reason = ?
            WHERE id = ?""",
        (when, relevance, persona, filter_reason, prospect_id),
    )
    conn.commit()


def mark_drafted(
    conn: sqlite3.Connection, prospect_id: int,
    subject: str, body: str, when: str,
) -> None:
    conn.execute(
        """UPDATE prospects
              SET drafted_at = ?, draft_subject = ?, draft_body = ?
            WHERE id = ?""",
        (when, subject, body, prospect_id),
    )
    conn.commit()


def stats(conn: sqlite3.Connection) -> dict:
    def one(q: str) -> int:
        return conn.execute(q).fetchone()[0]
    return {
        "total":          one("SELECT COUNT(*) FROM prospects"),
        "classified":     one("SELECT COUNT(*) FROM prospects WHERE classified_at IS NOT NULL"),
        "filtered":       one("SELECT COUNT(*) FROM prospects WHERE filter_reason IS NOT NULL"),
        "qualified":      one("SELECT COUNT(*) FROM prospects WHERE filter_reason IS NULL AND relevance >= 3"),
        "drafted":        one("SELECT COUNT(*) FROM prospects WHERE drafted_at IS NOT NULL"),
        "sent":           one("SELECT COUNT(*) FROM prospects WHERE sent_at IS NOT NULL"),
        "persona_finance":one("SELECT COUNT(*) FROM prospects WHERE persona = 'finance'"),
        "persona_broad":  one("SELECT COUNT(*) FROM prospects WHERE persona = 'broad'"),
    }
