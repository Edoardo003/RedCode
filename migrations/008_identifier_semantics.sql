CREATE TABLE IF NOT EXISTS identifier_registry (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  fingerprint TEXT NOT NULL,
  roles_json TEXT NOT NULL DEFAULT '[]',
  contexts_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(engagement_id, fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_identifier_registry_engagement
  ON identifier_registry(engagement_id);
