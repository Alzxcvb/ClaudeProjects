"""SQLite access. Schema is created on every connect (idempotent DDL)."""
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def connect(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def latest_metrics(conn, run_id):
    """The most recent snapshot for a run. Scoring always uses this row;
    checkpoint labels only matter for the logging workflow."""
    return conn.execute(
        "SELECT * FROM metrics WHERE run_id = ? ORDER BY captured_at DESC, id DESC LIMIT 1",
        (run_id,),
    ).fetchone()
