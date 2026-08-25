CREATE TABLE IF NOT EXISTS policy_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  source_url TEXT,
  snapshot_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  reviewed_by TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'reviewed'
    CHECK(status IN ('draft','reviewed','stale','superseded')),
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS program_scope_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  rule TEXT NOT NULL,
  disposition TEXT NOT NULL CHECK(disposition IN ('allow','deny')),
  source_snapshot_id INTEGER REFERENCES policy_snapshots(id),
  active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(engagement_id, rule, disposition, active)
);

CREATE TABLE IF NOT EXISTS program_restrictions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  action TEXT NOT NULL,
  reason TEXT NOT NULL,
  source_snapshot_id INTEGER REFERENCES policy_snapshots(id),
  active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(engagement_id, action, reason, active)
);

CREATE TABLE IF NOT EXISTS burp_import_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  source_kind TEXT NOT NULL CHECK(source_kind IN ('history','site_map','export')),
  source_path TEXT,
  source_sha256 TEXT,
  cursor_value TEXT,
  messages_seen INTEGER NOT NULL DEFAULT 0,
  messages_imported INTEGER NOT NULL DEFAULT 0,
  messages_skipped INTEGER NOT NULL DEFAULT 0,
  redacted_fields INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'running'
    CHECK(status IN ('running','completed','failed')),
  error TEXT,
  started_at TEXT DEFAULT (datetime('now')),
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS burp_message_refs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  import_run_id INTEGER REFERENCES burp_import_runs(id),
  endpoint_id INTEGER NOT NULL REFERENCES endpoints(id),
  identity_id INTEGER REFERENCES identities(id),
  message_ref TEXT NOT NULL,
  method TEXT NOT NULL,
  url TEXT NOT NULL,
  request_artifact_path TEXT,
  request_sha256 TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(engagement_id, message_ref)
);

CREATE TABLE IF NOT EXISTS test_plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  hypothesis_id INTEGER NOT NULL REFERENCES hypotheses(id),
  action TEXT NOT NULL,
  target TEXT NOT NULL,
  method TEXT NOT NULL,
  path_template TEXT NOT NULL,
  identity_label TEXT,
  max_requests INTEGER NOT NULL CHECK(max_requests BETWEEN 1 AND 20),
  rate_limit_per_second INTEGER NOT NULL CHECK(rate_limit_per_second >= 1),
  plan_json TEXT NOT NULL,
  plan_sha256 TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK(status IN ('draft','approved','testing','completed','expired','superseded','cancelled')),
  approval_id INTEGER REFERENCES approvals(id),
  approved_by TEXT,
  approved_at TEXT,
  expires_at TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS approval_executions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  test_plan_id INTEGER NOT NULL REFERENCES test_plans(id),
  status TEXT NOT NULL DEFAULT 'started'
    CHECK(status IN ('started','completed','failed','cancelled')),
  request_count INTEGER NOT NULL DEFAULT 0 CHECK(request_count >= 0),
  evidence_path TEXT,
  evidence_sha256 TEXT,
  result_summary TEXT,
  started_at TEXT DEFAULT (datetime('now')),
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS hypothesis_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  hypothesis_id INTEGER NOT NULL REFERENCES hypotheses(id),
  event_type TEXT NOT NULL,
  from_status TEXT,
  to_status TEXT,
  actor TEXT,
  details_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_policy_snapshots_engagement
  ON policy_snapshots(engagement_id, reviewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_program_scope_rules_engagement
  ON program_scope_rules(engagement_id, active, disposition);
CREATE INDEX IF NOT EXISTS idx_burp_import_runs_engagement
  ON burp_import_runs(engagement_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_burp_message_refs_endpoint
  ON burp_message_refs(endpoint_id);
CREATE INDEX IF NOT EXISTS idx_test_plans_hypothesis
  ON test_plans(hypothesis_id, status, expires_at);
CREATE INDEX IF NOT EXISTS idx_approval_executions_plan
  ON approval_executions(test_plan_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_hypothesis_events_hypothesis
  ON hypothesis_events(hypothesis_id, created_at DESC);
