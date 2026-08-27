ALTER TABLE application_workflows
  ADD COLUMN semantics_json TEXT NOT NULL DEFAULT '{}';

ALTER TABLE hypotheses
  ADD COLUMN semantic_key TEXT;

ALTER TABLE hypotheses
  ADD COLUMN reasoning_json TEXT NOT NULL DEFAULT '{}';

CREATE UNIQUE INDEX IF NOT EXISTS idx_hypotheses_semantic_identity
  ON hypotheses(engagement_id, semantic_key);
