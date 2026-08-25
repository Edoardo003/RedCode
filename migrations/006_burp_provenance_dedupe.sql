ALTER TABLE burp_message_refs
  ADD COLUMN source_message_ref TEXT;

ALTER TABLE burp_message_refs
  ADD COLUMN request_fingerprint TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_burp_message_refs_fingerprint
  ON burp_message_refs(engagement_id, request_fingerprint);
