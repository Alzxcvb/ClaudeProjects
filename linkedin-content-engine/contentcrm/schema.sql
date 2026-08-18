-- Content CRM schema.
-- The model: an idea is durable; a variant is one written expression of an
-- idea for one platform (variants have parents); a run is one publication of
-- one variant at one moment. Metrics attach to runs, as dated snapshots.
-- Collapsing these three is what made posts.jsonl a dead end.

CREATE TABLE IF NOT EXISTS ideas (
    id          INTEGER PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    thesis      TEXT,
    source      TEXT NOT NULL DEFAULT 'manual',   -- manual | posts.jsonl | markdown-import
    source_path TEXT,
    tags        TEXT NOT NULL DEFAULT '[]',       -- JSON array
    status      TEXT NOT NULL DEFAULT 'active',   -- active | retired
    created_at  TEXT NOT NULL,
    notes       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS variants (
    id                      INTEGER PRIMARY KEY,
    idea_id                 INTEGER NOT NULL REFERENCES ideas(id),
    platform                TEXT NOT NULL,
    derived_from_variant_id INTEGER REFERENCES variants(id),
    body                    TEXT,                 -- NULL = body not recorded
    hook_archetype          TEXT,
    format                  TEXT,
    cta_type                TEXT,
    media_type              TEXT,
    stage                   INTEGER,              -- funnel stage 1-4, see RUNBOOK
    word_count              INTEGER,
    hashtags                TEXT NOT NULL DEFAULT '[]',
    legacy_post_id          TEXT UNIQUE,          -- posts.jsonl id (post-001 ...)
    source_path             TEXT,
    content_hash            TEXT,
    created_at              TEXT NOT NULL,
    notes                   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS runs (
    id                  INTEGER PRIMARY KEY,
    variant_id          INTEGER NOT NULL REFERENCES variants(id),
    platform            TEXT NOT NULL,
    posted_at           TEXT NOT NULL,            -- 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD'
    posted_at_precision TEXT NOT NULL DEFAULT 'minute',  -- minute | date | approx
    dow_bucket          TEXT,                     -- Mon..Sun; NULL when date is approx
    slot_bucket         TEXT,                     -- config slot name; NULL when time unknown
    followers_at_post   INTEGER,                  -- NULL = not recorded; kills normalised reach
    post_url            TEXT,
    post_urn            TEXT,                     -- urn:li:share:... captured at publish; NULL = published by hand
    comment_authors     TEXT NOT NULL DEFAULT '[]',
    legacy_post_id      TEXT UNIQUE,
    created_at          TEXT NOT NULL,
    notes               TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS metrics (
    id             INTEGER PRIMARY KEY,
    run_id         INTEGER NOT NULL REFERENCES runs(id),
    checkpoint     TEXT,                          -- '24h' | '72h' | '7d' | NULL = ad hoc
    captured_at    TEXT NOT NULL,
    impressions    INTEGER,
    reactions      INTEGER,
    comments       INTEGER,
    reposts        INTEGER,
    saves          INTEGER,
    link_clicks    INTEGER,
    profile_visits INTEGER,
    bookings       INTEGER,
    notes          TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_variants_idea   ON variants(idea_id);
CREATE INDEX IF NOT EXISTS idx_variants_parent ON variants(derived_from_variant_id);
CREATE INDEX IF NOT EXISTS idx_runs_variant    ON runs(variant_id);
CREATE INDEX IF NOT EXISTS idx_runs_platform   ON runs(platform, posted_at);
CREATE INDEX IF NOT EXISTS idx_metrics_run     ON metrics(run_id, captured_at);
-- One live post maps to exactly one run. This is the database-level guard
-- against the duplicate-repost failure that has happened three times.
CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_post_urn ON runs(post_urn) WHERE post_urn IS NOT NULL;
