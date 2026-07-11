PRAGMA foreign_keys = ON;
PRAGMA user_version = 2;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES (2, 'control_plane');

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

CREATE INDEX IF NOT EXISTS idx_assets_engagement ON assets(engagement_id);
CREATE INDEX IF NOT EXISTS idx_findings_target_phase ON findings(target_id, phase);
CREATE INDEX IF NOT EXISTS idx_findings_engagement ON findings(engagement_id);
CREATE INDEX IF NOT EXISTS idx_findings_asset ON findings(asset_id);
CREATE INDEX IF NOT EXISTS idx_scans_target_status ON scans(target_id, status);
CREATE INDEX IF NOT EXISTS idx_scans_engagement_phase ON scans(engagement_id, phase);
CREATE INDEX IF NOT EXISTS idx_scans_asset ON scans(asset_id);
CREATE INDEX IF NOT EXISTS idx_approvals_engagement ON approvals(engagement_id);
CREATE INDEX IF NOT EXISTS idx_evidence_finding ON evidence(finding_id);
