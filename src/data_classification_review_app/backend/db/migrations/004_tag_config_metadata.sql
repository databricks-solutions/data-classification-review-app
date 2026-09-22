CREATE TABLE IF NOT EXISTS tag_policy_cache (
  tag_key        TEXT PRIMARY KEY,
  description    TEXT,
  allowed_values TEXT[] NOT NULL DEFAULT '{}'
);
