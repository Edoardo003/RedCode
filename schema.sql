CREATE TABLE IF NOT EXISTS targets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain TEXT NOT NULL UNIQUE,
  scope TEXT,
  type TEXT DEFAULT 'web',
  status TEXT DEFAULT 'active',
  created_at TEXT DEFAULT (datetime('now')),
  notes TEXT
);

CREATE TABLE IF NOT EXISTS findings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
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
  target_id INTEGER REFERENCES targets(id),
  tool TEXT NOT NULL,
  command TEXT,
  started_at TEXT DEFAULT (datetime('now')),
  ended_at TEXT,
  status TEXT DEFAULT 'running' CHECK(status IN ('running','completed','failed','cancelled')),
  output_path TEXT,
  finding_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS credentials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
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
