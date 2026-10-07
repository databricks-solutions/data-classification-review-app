# Data Classification Review — Release Notes v1.1.0

**Release date:** October 2026<br>
**Type:** Minor release (v1.0.2 → v1.1.0)<br>
**Test status:** `uv run --frozen --with pgserver pytest -q` — 199 passed, 0 failed

---

## Highlights

The release 1.1.0 is introducing relevant performance optimizations necessary to handle large classified states, such as thousands of catalogs and tables. 

Minor fixes regarding record review per class tag and simplifications in the installation scripts are introduced as well.

- **Proposals served from a Lakebase synced table ([#2](https://github.com/databricks-solutions/data-classification-review-app/issues/2))** — the app no longer reads `system.data_classification.results` live through a SQL warehouse on every page load. A deduplicating Unity Catalog view feeds a `SNAPSHOT` Lakebase synced table, refreshed by a scheduled `classification_sync` job (every 24 h by default, `--sync-interval-hours`). This removes a limitation on large estates ([#1](https://github.com/databricks-solutions/data-classification-review-app/issues/1)).
- **The app service principal provisions and owns the read path ([#5](https://github.com/databricks-solutions/data-classification-review-app/issues/5))** — at every startup the app, as its service principal, creates or updates the view, the synced table and the sync job (idempotent). The job runs as the service principal without a `run_as` override, so the "Service Principal User" role is no longer needed. The service principal no longer needs `DATABRICKS_SUPERUSER` either. This also resolves [#7](https://github.com/databricks-solutions/data-classification-review-app/issues/7) differently than proposed there: provisioning runs at app startup instead of from the sync job.
- **Server-side pagination and aggregation ([#13](https://github.com/databricks-solutions/data-classification-review-app/issues/13))** — the overview, All assets, steward inbox, stewards admin and Apply tags screens query paginated or aggregated results instead of downloading the whole estate. Each review loads only one table.
- **Review decisions per tag ([#6](https://github.com/databricks-solutions/data-classification-review-app/pull/6))** — a column with several proposed tags now has a separate decision for each tag. Previously all tags of a column shared one status, and Apply tags wrote only one of them.
- **Classification sync on the admin overview ([#8](https://github.com/databricks-solutions/data-classification-review-app/issues/8))** — shows the last sync time, a **Refresh** button and a *"sync pending"* state until the first sync completes. If provisioning fails, a banner shows the failed step, the error, the missing grant and the service principal to grant it to; **Retry setup** re-runs provisioning without restarting the app.
- **Add steward search on large or throttled workspaces ([#16](https://github.com/databricks-solutions/data-classification-review-app/issues/16))** — user and group search fail fast instead of hanging for minutes on SCIM rate limits. Where search by name is blocked, the dialog asks for the full email address. Email and username matches now work on every workspace.
- **Simpler Lakebase configuration** — an existing Lakebase instance is configured with just `--lakebase-endpoint-name` and `--lakebase-database`. The branch, host and database path are looked up from them.

---

## Breaking changes

| Change | What to do |
|---|---|
| **`deploy.sh` flags removed:** `--lakebase-branch`, `--lakebase-host`, and the path form of `--lakebase-database` (`projects/…/databases/…`). | Pass `--lakebase-endpoint-name` (read-write endpoint) and `--lakebase-database` with the Postgres database name (default `databricks_postgres`). |
| **App tables moved from Postgres `public` to the schema `data_classification_review_app`** ([#9](https://github.com/databricks-solutions/data-classification-review-app/issues/9)). The app never reads or moves the old tables, so after the upgrade it starts with empty decisions, steward assignments and tag configuration. | To keep your 1.0.x data, deploy with `--legacy-upgrade-job` (or answer *yes* to *"Upgrading from 1.0.x?"*), open the app once, then run the job *"Data Classification Review App - Migrate legacy schema from version 1.0.x"* ([#10](https://github.com/databricks-solutions/data-classification-review-app/issues/10), [#12](https://github.com/databricks-solutions/data-classification-review-app/issues/12)). |
| **The app now connects to the database given in `--lakebase-database`** ([#17](https://github.com/databricks-solutions/data-classification-review-app/issues/17)). 1.0.x always connected to `databricks_postgres`. | If you use the default `databricks_postgres`, nothing changes. Otherwise the existing data stays in `databricks_postgres` and is not copied automatically (see "Upgrading from 1.0.x" section). |
| **API:** `GET /api/proposals` is paginated (`page`, `page_size` ≤ 500) and `GET /api/tables` requires a `steward` parameter. | Only affects clients that call the API directly. |

---

### Upgrading from 1.0.x

1. Make sure the grants descripted in the deployment guide are in place or let the deploy assign them.
2. Run `./scripts/deploy.sh` with the new Lakebase flags. Add `--legacy-upgrade-job` if you want to keep the 1.0.x data.
3. Wait for the deploy to report that the app has provisioned the view, synced table and sync job. Until the first sync completes, the app shows *"Classification sync pending"*.
4. If you opted in, run the migration job (**Run now**, or `databricks bundle run data-classification-review-legacy-upgrade -t prod`). It copies the rows in one transaction, keeps rows the app already has, and later runs do nothing. Run it with `dry_run = true` to preview the row counts, or `drop_legacy = true` to remove the old tables once copied.

Decisions are migrated to per-tag automatically. Decisions recorded before 1.1.0 apply to every tag of their column until a steward records a decision for a specific tag.

---

## Installer changes

- New `--classification-catalog` / `--classification-schema` (default `data_classification_review_app.default`, created if missing) ([#11](https://github.com/databricks-solutions/data-classification-review-app/issues/11)), plus `--classification-view`, `--synced-table` and `--sync-interval-hours`. Interactive installs prompt for the catalog and schema ([#4](https://github.com/databricks-solutions/data-classification-review-app/issues/4)).
- `--skip-permission-assignment`, and an interactive *"Assign the required grants/permissions during this deploy?"* prompt. The deploy attempts every grant, then lists all the ones that failed along with the full required set, and stops before starting the app.
- `--legacy-upgrade-job`, and an interactive *"Upgrading from 1.0.x?"* prompt (default *no*).
- A single `bundle deploy`. The deploy then waits for the app to provision the read path for the version just deployed.
- The deploy grants the deployer and the `--admin-emails` users **Can Manage** on the sync job.

---

## Fixes

- **Cold warehouse** ([#15](https://github.com/databricks-solutions/data-classification-review-app/issues/15)) — a statement still `PENDING` after the 30 s submit window (for example, while a stopped serverless warehouse starts) is now polled until it finishes.
- **Lakebase database** ([#17](https://github.com/databricks-solutions/data-classification-review-app/issues/17), first reported in [#3](https://github.com/databricks-solutions/data-classification-review-app/pull/3)) — the app and the synced table use the same database provided during the installation process.
- **Multi-tag columns** ([#6](https://github.com/databricks-solutions/data-classification-review-app/pull/6)) — Apply tags no longer drops all but one tag of a column, and the All assets search no longer shows stale rows from duplicate keys.
- **Steward search** ([#16](https://github.com/databricks-solutions/data-classification-review-app/issues/16)) — fixed SCIM user filtering

---

## Known limitations

- **Recreating the app or replacing its service principal requires manual repair** ([#19](https://github.com/databricks-solutions/data-classification-review-app/issues/19)). The app schema, the synced-table access and the classification view and job are tied to the service principal that created them. With a new service principal the app fails to start or can't read proposals.