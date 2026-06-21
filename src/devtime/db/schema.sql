-- DevTime V0 SQLite schema (Builder Edition, Chapter 6 + Appendix C).
-- The database is the local memory layer.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS repositories (
    id TEXT PRIMARY KEY,
    root_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scans (
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    devtime_version TEXT NOT NULL,
    file_count INTEGER DEFAULT 0,
    signal_count INTEGER DEFAULT 0,
    FOREIGN KEY(repository_id) REFERENCES repositories(id)
);

CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL,
    path TEXT NOT NULL,
    extension TEXT,
    language TEXT,
    sha256 TEXT,
    size_bytes INTEGER,
    is_test INTEGER DEFAULT 0,
    is_doc INTEGER DEFAULT 0,
    ignored INTEGER DEFAULT 0,
    last_seen_scan_id TEXT,
    UNIQUE(repository_id, path)
);

CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY,
    scan_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    name TEXT,
    value TEXT,
    start_line INTEGER,
    end_line INTEGER,
    confidence REAL DEFAULT 0.5,
    metadata_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS concepts (
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    kind TEXT NOT NULL,
    summary TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'proposed',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(repository_id, slug)
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    concept_id TEXT NOT NULL,
    file_id TEXT,
    signal_id TEXT,
    kind TEXT NOT NULL,
    strength TEXT NOT NULL,
    summary TEXT NOT NULL,
    path TEXT,
    start_line INTEGER,
    end_line INTEGER,
    metadata_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(concept_id) REFERENCES concepts(id)
);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    concept_id TEXT NOT NULL,
    type TEXT NOT NULL,
    text TEXT NOT NULL,
    confidence REAL NOT NULL,
    state TEXT NOT NULL DEFAULT 'supported',
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    uncertainty_ids_json TEXT NOT NULL DEFAULT '[]',
    requires_human_confirmation INTEGER DEFAULT 0,
    created_by TEXT NOT NULL DEFAULT 'machine',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_verified_at TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    concept_id TEXT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'human',
    status TEXT NOT NULL DEFAULT 'active',
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS uncertainties (
    id TEXT PRIMARY KEY,
    concept_id TEXT NOT NULL,
    type TEXT NOT NULL,
    text TEXT NOT NULL,
    action TEXT,
    severity TEXT DEFAULT 'medium',
    evidence_gap_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_findings (
    id TEXT PRIMARY KEY,
    concept_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    type TEXT NOT NULL,
    text TEXT NOT NULL,
    evidence_ids_json TEXT DEFAULT '[]',
    changed_files_json TEXT DEFAULT '[]',
    suggested_action TEXT,
    human_review_required INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS context_packs (
    id TEXT PRIMARY KEY,
    concept_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    body_markdown TEXT NOT NULL,
    metadata_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);
