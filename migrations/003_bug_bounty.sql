CREATE TABLE IF NOT EXISTS bug_bounty_programs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id INTEGER NOT NULL UNIQUE REFERENCES engagements(id),
  platform TEXT NOT NULL DEFAULT 'hackerone', program_name TEXT NOT NULL,
  program_url TEXT, policy_url TEXT, policy_snapshot_path TEXT, currency TEXT,
  minimum_bounty REAL, maximum_bounty REAL, response_sla_hours INTEGER,
  duplicate_risk INTEGER CHECK(duplicate_risk BETWEEN 0 AND 5),
  account_requirements TEXT, opportunity_score REAL, notes TEXT,
  created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS identities (
  id INTEGER PRIMARY KEY AUTOINCREMENT, engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  target_id INTEGER REFERENCES targets(id), label TEXT NOT NULL, tenant TEXT, role TEXT,
  auth_state TEXT, burp_label TEXT, notes TEXT, created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')), UNIQUE(engagement_id, label)
);
CREATE TABLE IF NOT EXISTS endpoints (
  id INTEGER PRIMARY KEY AUTOINCREMENT, engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  target_id INTEGER REFERENCES targets(id), asset_id INTEGER REFERENCES assets(id),
  endpoint_key TEXT NOT NULL, host TEXT NOT NULL, method TEXT NOT NULL, path_template TEXT NOT NULL,
  protocol TEXT NOT NULL DEFAULT 'http', content_type TEXT, object_type TEXT,
  state_change INTEGER NOT NULL DEFAULT 0 CHECK(state_change IN (0,1)),
  auth_required INTEGER CHECK(auth_required IN (0,1)), source TEXT NOT NULL DEFAULT 'burp',
  coverage_status TEXT NOT NULL DEFAULT 'observed' CHECK(coverage_status IN ('observed','mapped','tested','blocked','out_of_scope')),
  burp_history_refs TEXT NOT NULL DEFAULT '[]', metadata_json TEXT NOT NULL DEFAULT '{}',
  first_seen_at TEXT DEFAULT (datetime('now')), last_seen_at TEXT DEFAULT (datetime('now')),
  UNIQUE(engagement_id, endpoint_key)
);
CREATE TABLE IF NOT EXISTS application_workflows (
  id INTEGER PRIMARY KEY AUTOINCREMENT, engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  target_id INTEGER REFERENCES targets(id), workflow_key TEXT NOT NULL, name TEXT NOT NULL,
  states_json TEXT NOT NULL DEFAULT '[]', actors_json TEXT NOT NULL DEFAULT '[]',
  objects_json TEXT NOT NULL DEFAULT '[]', sensitivity INTEGER NOT NULL DEFAULT 0 CHECK(sensitivity BETWEEN 0 AND 5),
  notes TEXT, created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(engagement_id, workflow_key)
);
CREATE TABLE IF NOT EXISTS hypotheses (
  id INTEGER PRIMARY KEY AUTOINCREMENT, engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  target_id INTEGER REFERENCES targets(id), endpoint_id INTEGER REFERENCES endpoints(id),
  workflow_id INTEGER REFERENCES application_workflows(id), hypothesis_id TEXT NOT NULL UNIQUE,
  statement TEXT NOT NULL, actor_label TEXT, action TEXT, object_owner TEXT, object_state TEXT, channel TEXT,
  boundary_score INTEGER NOT NULL DEFAULT 0 CHECK(boundary_score BETWEEN 0 AND 5),
  impact_score INTEGER NOT NULL DEFAULT 0 CHECK(impact_score BETWEEN 0 AND 5),
  novelty_score INTEGER NOT NULL DEFAULT 0 CHECK(novelty_score BETWEEN 0 AND 5),
  evidence_score INTEGER NOT NULL DEFAULT 0 CHECK(evidence_score BETWEEN 0 AND 5),
  duplicate_risk INTEGER NOT NULL DEFAULT 0 CHECK(duplicate_risk BETWEEN 0 AND 5),
  test_cost INTEGER NOT NULL DEFAULT 0 CHECK(test_cost BETWEEN 0 AND 5),
  operational_risk INTEGER NOT NULL DEFAULT 0 CHECK(operational_risk BETWEEN 0 AND 5),
  priority INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','approved','testing','rejected','candidate','confirmed','duplicate','informative')),
  evidence_refs TEXT NOT NULL DEFAULT '[]', notes TEXT,
  created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS hunt_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  target_id INTEGER REFERENCES targets(id), objective TEXT,
  status TEXT NOT NULL DEFAULT 'running' CHECK(status IN ('running','completed','paused','failed')),
  endpoints_seen INTEGER NOT NULL DEFAULT 0, hypotheses_tested INTEGER NOT NULL DEFAULT 0,
  findings_confirmed INTEGER NOT NULL DEFAULT 0, notes TEXT,
  started_at TEXT DEFAULT (datetime('now')), ended_at TEXT
);
CREATE TABLE IF NOT EXISTS bug_bounty_submissions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, engagement_id INTEGER NOT NULL REFERENCES engagements(id),
  finding_id INTEGER REFERENCES findings(id), platform TEXT NOT NULL DEFAULT 'hackerone', external_id TEXT,
  status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','submitted','triaged','duplicate','informative','accepted','rejected','paid')),
  reward_amount REAL, currency TEXT, submitted_at TEXT, resolved_at TEXT, notes TEXT,
  created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(platform, external_id)
);
CREATE INDEX IF NOT EXISTS idx_programs_engagement ON bug_bounty_programs(engagement_id);
CREATE INDEX IF NOT EXISTS idx_identities_engagement ON identities(engagement_id);
CREATE INDEX IF NOT EXISTS idx_endpoints_engagement_host ON endpoints(engagement_id, host);
CREATE INDEX IF NOT EXISTS idx_endpoints_coverage ON endpoints(engagement_id, coverage_status);
CREATE INDEX IF NOT EXISTS idx_workflows_engagement ON application_workflows(engagement_id);
CREATE INDEX IF NOT EXISTS idx_hypotheses_queue ON hypotheses(engagement_id, status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_hunt_sessions_engagement ON hunt_sessions(engagement_id, started_at);
CREATE INDEX IF NOT EXISTS idx_submissions_engagement ON bug_bounty_submissions(engagement_id, status);
