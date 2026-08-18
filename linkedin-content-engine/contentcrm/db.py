"""SQLite access. Schema is created on every connect (idempotent DDL)."""
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


# Additive columns introduced after the first databases were created. Each entry
# is (table, column, type). ALTER TABLE ADD COLUMN is not idempotent, so these
# run only when the column is genuinely absent, and they run BEFORE schema.sql
# so that any index in that file can safely reference the new column.
MIGRATIONS = [
    ("runs", "post_urn", "TEXT"),
]


def _migrate(conn):
    for table, column, coltype in MIGRATIONS:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            continue  # fresh database; schema.sql creates the column itself
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(%s)" % table)}
        if column not in cols:
            conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, coltype))
    conn.commit()


def connect(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _migrate(conn)
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def latest_metrics(conn, run_id):
    """The most recent snapshot for a run. Scoring always uses this row;
    checkpoint labels only matter for the logging workflow."""
    return conn.execute(
        "SELECT * FROM metrics WHERE run_id = ? ORDER BY captured_at DESC, id DESC LIMIT 1",
        (run_id,),
    ).fetchone()
