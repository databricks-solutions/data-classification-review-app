-- Review decisions are per proposal — one (catalog, schema, table, column, class_tag), the
-- synced table's primary key — not per column.
--
-- `decisions` stays the append-only history (it is also the admin audit log, whose
-- column_key is "steward:…" / "assignment:…"). Its column_key is split into the synced
-- table's key columns; they are NULL for audit rows and malformed keys.
-- Column names may contain dots: catalog/schema/table can't, so the first three split.
ALTER TABLE decisions
  ADD COLUMN IF NOT EXISTS catalog_name TEXT GENERATED ALWAYS AS (CASE
    WHEN status IN ('pending', 'approved', 'rejected', 'modified', 'applied')
    THEN (regexp_match(column_key, '^([^.]*)\.([^.]*)\.([^.]*)\.(.*)$'))[1] END) STORED,
  ADD COLUMN IF NOT EXISTS schema_name TEXT GENERATED ALWAYS AS (CASE
    WHEN status IN ('pending', 'approved', 'rejected', 'modified', 'applied')
    THEN (regexp_match(column_key, '^([^.]*)\.([^.]*)\.([^.]*)\.(.*)$'))[2] END) STORED,
  ADD COLUMN IF NOT EXISTS table_name TEXT GENERATED ALWAYS AS (CASE
    WHEN status IN ('pending', 'approved', 'rejected', 'modified', 'applied')
    THEN (regexp_match(column_key, '^([^.]*)\.([^.]*)\.([^.]*)\.(.*)$'))[3] END) STORED,
  ADD COLUMN IF NOT EXISTS column_name TEXT GENERATED ALWAYS AS (CASE
    WHEN status IN ('pending', 'approved', 'rejected', 'modified', 'applied')
    THEN (regexp_match(column_key, '^([^.]*)\.([^.]*)\.([^.]*)\.(.*)$'))[4] END) STORED;

-- The current decision of every proposal, so reads don't re-derive it from the history.
-- class_tag is the proposal's tag: the scanner's class_tag, or for a steward-added
-- proposal the tag they added (decisions.modified_tag). '' marks a decision recorded
-- before decisions carried a class_tag; it covers every tag of its column.
CREATE TABLE IF NOT EXISTS proposal_state (
  catalog_name  TEXT NOT NULL,
  schema_name   TEXT NOT NULL,
  table_name    TEXT NOT NULL,
  column_name   TEXT NOT NULL,
  class_tag     TEXT NOT NULL,
  user_added    BOOLEAN NOT NULL,
  status        TEXT NOT NULL,
  modified_tag  TEXT,
  comment       TEXT,
  reviewer      TEXT NOT NULL,
  decided_at    TIMESTAMPTZ NOT NULL,
  applied_at    TIMESTAMPTZ,
  PRIMARY KEY (catalog_name, schema_name, table_name, column_name, class_tag, user_added)
);

-- Kept current by a trigger rather than by each route, so every writer — the routes, the
-- mock seed and the legacy-copy notebook (which inserts old history in any order) —
-- updates it. Only a decision at least as new as the stored one replaces it.
-- search_path is pinned to the app schema: the notebook's session doesn't set it.
CREATE OR REPLACE FUNCTION decisions_to_proposal_state() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
BEGIN
  IF NEW.catalog_name IS NULL THEN
    RETURN NULL;
  END IF;
  INSERT INTO proposal_state AS ps (catalog_name, schema_name, table_name, column_name,
    class_tag, user_added, status, modified_tag, comment, reviewer, decided_at, applied_at)
  VALUES (NEW.catalog_name, NEW.schema_name, NEW.table_name, NEW.column_name,
    CASE WHEN NEW.user_added THEN COALESCE(NEW.modified_tag, NEW.class_tag, '')
         ELSE COALESCE(NEW.class_tag, '') END,
    NEW.user_added, NEW.status, NEW.modified_tag, NEW.comment, NEW.reviewer,
    NEW.decided_at, NEW.applied_at)
  ON CONFLICT (catalog_name, schema_name, table_name, column_name, class_tag, user_added)
  DO UPDATE SET status = EXCLUDED.status, modified_tag = EXCLUDED.modified_tag,
    comment = EXCLUDED.comment, reviewer = EXCLUDED.reviewer,
    decided_at = EXCLUDED.decided_at, applied_at = EXCLUDED.applied_at
  WHERE EXCLUDED.decided_at >= ps.decided_at;
  RETURN NULL;
END $$;

-- Backfill from the history recorded so far: the latest decision per proposal.
INSERT INTO proposal_state (catalog_name, schema_name, table_name, column_name, class_tag,
  user_added, status, modified_tag, comment, reviewer, decided_at, applied_at)
SELECT DISTINCT ON (1, 2, 3, 4, 5, 6) * FROM (
  SELECT catalog_name, schema_name, table_name, column_name,
         CASE WHEN user_added THEN COALESCE(modified_tag, class_tag, '')
              ELSE COALESCE(class_tag, '') END AS class_tag,
         user_added, status, modified_tag, comment, reviewer, decided_at, applied_at
  FROM decisions WHERE catalog_name IS NOT NULL
) d
ORDER BY 1, 2, 3, 4, 5, 6, decided_at DESC
ON CONFLICT DO NOTHING;

DROP TRIGGER IF EXISTS decisions_proposal_state ON decisions;
CREATE TRIGGER decisions_proposal_state AFTER INSERT ON decisions
  FOR EACH ROW EXECUTE FUNCTION decisions_to_proposal_state();
