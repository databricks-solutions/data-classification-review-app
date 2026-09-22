CREATE TABLE IF NOT EXISTS principals (
  id        TEXT PRIMARY KEY,
  name      TEXT NOT NULL,
  email     TEXT,
  kind      TEXT NOT NULL DEFAULT 'user',
  initials  TEXT NOT NULL DEFAULT '??',
  accent    TEXT NOT NULL DEFAULT '#1B3139',
  team      TEXT,
  members   INT,
  is_admin  BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS steward_assignments (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  principal       TEXT NOT NULL REFERENCES principals(id) ON DELETE CASCADE,
  principal_kind  TEXT NOT NULL DEFAULT 'user',
  scope           TEXT NOT NULL,
  catalog         TEXT NOT NULL,
  schema_name     TEXT,
  table_name      TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  column_key    TEXT NOT NULL,
  scan_ts       TIMESTAMPTZ,
  status        TEXT NOT NULL DEFAULT 'pending',
  modified_tag  TEXT,
  comment       TEXT,
  reviewer      TEXT NOT NULL,
  decided_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  user_added    BOOLEAN NOT NULL DEFAULT false,
  applied_at    TIMESTAMPTZ
);

-- Non-unique index for efficient latest-decision lookups
CREATE INDEX IF NOT EXISTS decisions_col_decided_idx
  ON decisions (column_key, decided_at DESC) WHERE user_added = false;
