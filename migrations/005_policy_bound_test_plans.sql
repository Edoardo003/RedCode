ALTER TABLE test_plans
  ADD COLUMN policy_snapshot_id INTEGER REFERENCES policy_snapshots(id);

CREATE INDEX IF NOT EXISTS idx_test_plans_policy_snapshot
  ON test_plans(policy_snapshot_id, status);
