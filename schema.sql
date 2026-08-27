PRAGMA foreign_keys = ON;
PRAGMA user_version = 6;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES (2, 'control_plane');
INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES (3, 'bug_bounty_state');
INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES (4, 'bug_bounty_assistant');
INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES (5, 'policy_bound_test_plans');
INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES (6, 'burp_provenance_dedupe');

CREATE TABLE IF NOT EXISTS engagements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_key TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  workflow TEXT NOT NULL CHECK(workflow IN ('assessment','ctf')),
  mode TEXT NOT NULL DEFAULT 'normal' CHECK(mode IN ('normal','aggressive')),
  manifest_path TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','completed','archived')),
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS targets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain TEXT NOT NULL UNIQUE,
  scope TEXT,
  type TEXT DEFAULT 'web',
  status TEXT DEFAULT 'active',
  created_at TEXT DEFAULT (datetime('now')),
  notes TEXT
);

CREATE TABLE IF NOT EXISTS assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER REFERENCES engagements(id),
  target_id INTEGER REFERENCES targets(id),
  kind TEXT NOT NULL DEFAULT 'host',
  value TEXT NOT NULL,
  in_scope INTEGER NOT NULL DEFAULT 1 CHECK(in_scope IN (0,1)),
  source TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','inactive','out_of_scope')),
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(engagement_id, value)
);

CREATE TABLE IF NOT EXISTS findings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER REFERENCES engagements(id),
  asset_id INTEGER REFERENCES assets(id),
  target_id INTEGER REFERENCES targets(id),
  finding_id TEXT UNIQUE NOT NULL,
  phase TEXT NOT NULL CHECK(phase IN ('recon','osint','scan','exploit','socialeng','report')),
  type TEXT NOT NULL,
  severity TEXT NOT NULL CHECK(severity IN ('critical','high','medium','low','info')),
  title TEXT NOT NULL,
  url TEXT,
  evidence TEXT,
  cvss REAL,
  cwe TEXT,
  confidence TEXT DEFAULT 'potential' CHECK(confidence IN ('confirmed','likely','potential','unverified')),
  status TEXT DEFAULT 'new' CHECK(status IN ('new','confirmed','exploited','reported','fixed')),
  raw_path TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER REFERENCES engagements(id),
  asset_id INTEGER REFERENCES assets(id),
  target_id INTEGER REFERENCES targets(id),
  phase TEXT CHECK(phase IN ('recon','osint','scan','exploit','socialeng','report')),
  subdomain TEXT,
  tool TEXT NOT NULL,
  command TEXT,
  started_at TEXT DEFAULT (datetime('now')),
  ended_at TEXT,
  status TEXT DEFAULT 'running' CHECK(status IN ('running','completed','failed','cancelled')),
  exit_code INTEGER,
  error TEXT,
  output_path TEXT,
  finding_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS credentials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER REFERENCES engagements(id),
  asset_id INTEGER REFERENCES assets(id),
  target_id INTEGER REFERENCES targets(id),
  finding_id INTEGER REFERENCES findings(id),
  username TEXT,
  password TEXT,
  token TEXT,
  url TEXT,
  source TEXT,
  phase TEXT,
  verified INTEGER DEFAULT 0,
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS approvals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  action TEXT NOT NULL,
  scope TEXT NOT NULL,
  approved_by TEXT,
  approved_at TEXT DEFAULT (datetime('now')),
  expires_at TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  finding_id INTEGER REFERENCES findings(id),
  scan_id INTEGER REFERENCES scans(id),
  path TEXT NOT NULL UNIQUE,
  sha256 TEXT,
  mime_type TEXT,
  size_bytes INTEGER,
  captured_at TEXT DEFAULT (datetime('now')),
  notes TEXT
);

CREATE TABLE IF NOT EXISTS finding_relations (
  source_finding_id INTEGER NOT NULL REFERENCES findings(id),
  target_finding_id INTEGER NOT NULL REFERENCES findings(id),
  relation TEXT NOT NULL CHECK(relation IN ('enables','depends_on','duplicates','confirms','contradicts')),
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY(source_finding_id, target_finding_id, relation)
);

CREATE TABLE IF NOT EXISTS bug_bounty_programs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER NOT NULL UNIQUE REFERENCES engagements(id),
  platform TEXT NOT NULL DEFAULT 'hackerone',
  program_name TEXT NOT NULL,
  program_url TEXT,
  policy_url TEXT,
  policy_snapshot_path TEXT,
  currency TEXT,
  minimum_bounty REAL,
  maximum_bounty REAL,
  response_sla_hours INTEGER,
  duplicate_risk INTEGER CHECK(duplicate_risk BETWEEN 0 AND 5),
  account_requirements TEXT,
  opportunity_score REAL,
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS identities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  target_id INTEGER REFERENCES targets(id),
  label TEXT NOT NULL,
  tenant TEXT,
  role TEXT,
  auth_state TEXT,
  burp_label TEXT,
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(engagement_id, label)
);

CREATE TABLE IF NOT EXISTS endpoints (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  target_id INTEGER REFERENCES targets(id),
  asset_id INTEGER REFERENCES assets(id),
  endpoint_key TEXT NOT NULL,
  host TEXT NOT NULL,
  method TEXT NOT NULL,
  path_template TEXT NOT NULL,
  protocol TEXT NOT NULL DEFAULT 'http',
  content_type TEXT,
  object_type TEXT,
  state_change INTEGER NOT NULL DEFAULT 0 CHECK(state_change IN (0,1)),
  auth_required INTEGER CHECK(auth_required IN (0,1)),
  source TEXT NOT NULL DEFAULT 'burp',
  coverage_status TEXT NOT NULL DEFAULT 'observed'
    CHECK(coverage_status IN ('observed','mapped','tested','blocked','out_of_scope')),
  burp_history_refs TEXT NOT NULL DEFAULT '[]',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  first_seen_at TEXT DEFAULT (datetime('now')),
  last_seen_at TEXT DEFAULT (datetime('now')),
  UNIQUE(engagement_id, endpoint_key)
);

CREATE TABLE IF NOT EXISTS application_workflows (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  target_id INTEGER REFERENCES targets(id),
  workflow_key TEXT NOT NULL,
  name TEXT NOT NULL,
  states_json TEXT NOT NULL DEFAULT '[]',
  actors_json TEXT NOT NULL DEFAULT '[]',
  objects_json TEXT NOT NULL DEFAULT '[]',
  sensitivity INTEGER NOT NULL DEFAULT 0 CHECK(sensitivity BETWEEN 0 AND 5),
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(engagement_id, workflow_key)
);

CREATE TABLE IF NOT EXISTS hypotheses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  target_id INTEGER REFERENCES targets(id),
  endpoint_id INTEGER REFERENCES endpoints(id),
  workflow_id INTEGER REFERENCES application_workflows(id),
  hypothesis_id TEXT NOT NULL UNIQUE,
  statement TEXT NOT NULL,
  actor_label TEXT,
  action TEXT,
  object_owner TEXT,
  object_state TEXT,
  channel TEXT,
  boundary_score INTEGER NOT NULL DEFAULT 0 CHECK(boundary_score BETWEEN 0 AND 5),
  impact_score INTEGER NOT NULL DEFAULT 0 CHECK(impact_score BETWEEN 0 AND 5),
  novelty_score INTEGER NOT NULL DEFAULT 0 CHECK(novelty_score BETWEEN 0 AND 5),
  evidence_score INTEGER NOT NULL DEFAULT 0 CHECK(evidence_score BETWEEN 0 AND 5),
  duplicate_risk INTEGER NOT NULL DEFAULT 0 CHECK(duplicate_risk BETWEEN 0 AND 5),
  test_cost INTEGER NOT NULL DEFAULT 0 CHECK(test_cost BETWEEN 0 AND 5),
  operational_risk INTEGER NOT NULL DEFAULT 0 CHECK(operational_risk BETWEEN 0 AND 5),
  priority INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'queued'
    CHECK(status IN ('queued','approved','testing','rejected','candidate','confirmed','duplicate','informative')),
  evidence_refs TEXT NOT NULL DEFAULT '[]',
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS hunt_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  target_id INTEGER REFERENCES targets(id),
  objective TEXT,
  status TEXT NOT NULL DEFAULT 'running'
    CHECK(status IN ('running','completed','paused','failed')),
  endpoints_seen INTEGER NOT NULL DEFAULT 0,
  hypotheses_tested INTEGER NOT NULL DEFAULT 0,
  findings_confirmed INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  started_at TEXT DEFAULT (datetime('now')),
  ended_at TEXT
);

CREATE TABLE IF NOT EXISTS bug_bounty_submissions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  finding_id INTEGER REFERENCES findings(id),
  platform TEXT NOT NULL DEFAULT 'hackerone',
  external_id TEXT,
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK(status IN ('draft','submitted','triaged','duplicate','informative','accepted','rejected','paid')),
  reward_amount REAL,
  currency TEXT,
  submitted_at TEXT,
  resolved_at TEXT,
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(platform, external_id)
);

CREATE INDEX IF NOT EXISTS idx_assets_engagement ON assets(engagement_id);
CREATE INDEX IF NOT EXISTS idx_findings_target_phase ON findings(target_id, phase);
CREATE INDEX IF NOT EXISTS idx_findings_engagement ON findings(engagement_id);
CREATE INDEX IF NOT EXISTS idx_findings_asset ON findings(asset_id);
CREATE INDEX IF NOT EXISTS idx_scans_target_status ON scans(target_id, status);
CREATE INDEX IF NOT EXISTS idx_scans_engagement_phase ON scans(engagement_id, phase);
CREATE INDEX IF NOT EXISTS idx_scans_asset ON scans(asset_id);
CREATE INDEX IF NOT EXISTS idx_approvals_engagement ON approvals(engagement_id);
CREATE INDEX IF NOT EXISTS idx_evidence_finding ON evidence(finding_id);
CREATE INDEX IF NOT EXISTS idx_programs_engagement ON bug_bounty_programs(engagement_id);
CREATE INDEX IF NOT EXISTS idx_identities_engagement ON identities(engagement_id);
CREATE INDEX IF NOT EXISTS idx_endpoints_engagement_host ON endpoints(engagement_id, host);
CREATE INDEX IF NOT EXISTS idx_endpoints_coverage ON endpoints(engagement_id, coverage_status);
CREATE INDEX IF NOT EXISTS idx_workflows_engagement ON application_workflows(engagement_id);
CREATE INDEX IF NOT EXISTS idx_hypotheses_queue ON hypotheses(engagement_id, status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_hunt_sessions_engagement ON hunt_sessions(engagement_id, started_at);
CREATE INDEX IF NOT EXISTS idx_submissions_engagement ON bug_bounty_submissions(engagement_id, status);

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
  source_message_ref TEXT,
  request_fingerprint TEXT,
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
  policy_snapshot_id INTEGER REFERENCES policy_snapshots(id),
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
CREATE UNIQUE INDEX IF NOT EXISTS idx_burp_message_refs_fingerprint
  ON burp_message_refs(engagement_id, request_fingerprint);
CREATE INDEX IF NOT EXISTS idx_test_plans_hypothesis
  ON test_plans(hypothesis_id, status, expires_at);
CREATE INDEX IF NOT EXISTS idx_test_plans_policy_snapshot
  ON test_plans(policy_snapshot_id, status);
CREATE INDEX IF NOT EXISTS idx_approval_executions_plan
  ON approval_executions(test_plan_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_hypothesis_events_hypothesis
  ON hypothesis_events(hypothesis_id, created_at DESC);
