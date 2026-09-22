# Data Classification Review

A Databricks App that puts data stewards in control of Unity Catalog ML-generated classification proposals.

## Overview

Databricks' Data Classification ([doc](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-classification)) in Unity Catalog automatically classifies and tag sensitive data in your catalog. Data catalogs can have a vast amount of data, often containing known and unknown sensitive data. It is critical for data teams to understand what kind of sensitive data exists in each table so that they can both govern and democratize access to this data.

A large organization can have hundreds of catalogs, tables and columns to review. The right people to validate whether a column actually contains PII are the **domain experts who own the data**.

**Data Classification Review** solves this by distributing the review workload across **data stewards** while keeping admins in control of scope and policy. Admins assign stewards to the specific tables they are accountable for; stewards get a focused inbox scoped to exactly those assets. They inspect column samples, accept, reject, or reassign each proposal, and submit their decisions, without needing high level Unity Catalog permissions on their own and respecting the visibility cones. Admins then apply the approved tags back to the catalog.

The result is a governed, distributed workflow: domain experts validate the data they know best, every decision is logged with reviewer identity and timestamp, and tags reach production only after explicit human approval.

## Key Features



### For Data Stewards

![Steward Overview](docs/images/Steward%20-%20Overview.png)

#### 📥 Inbox

A prioritised queue of pending proposals scoped to the tables the steward is assigned to. Each row shows the column name, the proposed classification tag, sample values, and any existing UC tags.

### For Admins

![Admin Overview](docs/images/Admin%20-%20Overview.png)

#### 🗂️ Asset Management

A full-catalog browser scoped to the configured catalog filter. Admins can drill into any table, see its current UC tags, manage steward assignments, and track review progress across the organization.

#### 👥 Steward Administration

Assign or remove stewards using catalog, schema or table granularity. The app enforces row-level access so each steward only sees the assets they are responsible for.

#### ⚙️ Tag Configuration

Maintain the canonical list of allowed classification tags through an in-app UI. Only configured tags appear in the steward picker, ensuring consistency across all reviewers.

#### 🏷️ Tag Application

Apply every approved decision to the Unity Catalog table metadata.

#### 📋 Audit Log

Every accept/reject/modify decision is persisted with the reviewer identity, timestamp, and the before/after tag values, providing a tamper-evident chain of custody.

## Deploying to Databricks



### Deploy from Pre-built Artifacts (Recommended)

Use this path for all standard deployments. The pre-built wheel and frontend assets are committed under `.build/` in the repository, no build tooling is needed.

#### Prerequisites for the deployment

- [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html) on your PATH
- Databricks workspace access
- Permission to create a Databricks App
- Permission to create a Lakehouse Project or use an existing one

The deploy script automatically grants the app's service principal the two permissions it needs to read classification proposals:

```sql
GRANT USE CATALOG ON CATALOG system TO `<sp-client-id>`;
GRANT SELECT ON TABLE system.data_classification.results TO `<sp-client-id>`;
```

These are the only Unity Catalog grants the service principal needs. Other interactions with Unity Catalog tables are routed through user's forwarded access token (OBO).

**The service principal client ID is printed partway through the deploy script (right after the app is created), so you have it on hand to run these GRANTs manually if the deployer identity can't apply them automatically. These grants currently can be assigned only by an account admin ([doc](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-classification#the-results-system-table)).**

#### Deployment script

The same `scripts/deploy.sh` script supports both an interactive (guided) and a non-interactive (flag-driven) path. Either way it deploys the app, configures Lakebase, and issues all required grants.

##### Clone project repository

```bash
git clone https://github.com/databricks-solutions/data-classification-review-app
cd data-classification-review-app
```



##### Interactive path

```bash
./scripts/deploy.sh
```

The script prompts for everything it needs:

- **Authentication** — choose environment variables (`DATABRICKS_HOST` + `DATABRICKS_TOKEN`) or an interactive `databricks auth login` profile.
- **Catalog filter** (default empty) — comma-separated catalog names that scope the entire app, limiting the app to read classification proposals from `system.data_classification.results` only to the listed catalogs. It is useful if you are planning to release multiple distinct app instances to segregate admin visibility cones. Leave it blank (default) to include all results.
- **Admin emails** — comma-separated admin addresses.
- **Warehouse** — pick from the numbered list of SQL warehouses in the workspace.
- **Lakebase** — point to an existing Autoscaling instance (branch, database, host, endpoint name) or provision a brand-new one.



##### Non-interactive path

Provide every required value as a flag and pass `--yes`; the script then runs end-to-end with no prompts. This is the path to use in CI or a Databricks web terminal.

```bash
# Env-var auth, existing Lakebase instance
export DATABRICKS_HOST=https://<your-workspace>.azuredatabricks.net
export DATABRICKS_TOKEN=dapi...

./scripts/deploy.sh \
  --admin-emails you@company.com \
  --warehouse-name "Shared Endpoint" \
  --catalog-filter my_catalog \
  --lakebase-branch        "projects/<id>/branches/production" \
  --lakebase-database      "projects/<id>/branches/production/databases/databricks-postgres" \
  --lakebase-host          "ep-xxx.database.azuredatabricks.net" \
  --lakebase-endpoint-name "projects/<id>/branches/production/endpoints/primary" \
  --yes
```


| Flag                                                                                         | Required                                                | Description                                                                                                                                                              |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--admin-emails LIST`                                                                        | yes                                                     | Comma-separated admin email addresses                                                                                                                                    |
| `--warehouse-name NAME`                                                                      | yes (non-interactive), unless `--warehouse-id` is given | SQL warehouse name (matched against the workspace warehouse list)                                                                                                        |
| `--warehouse-id ID`                                                                          | alternative to `--warehouse-name`                       | SQL warehouse ID — skips listing all warehouses; takes precedence over `--warehouse-name`                                                                                |
| `--catalog-filter LIST`                                                                      | no                                                      | Comma-separated catalog names to scope the app to (`CLASSIFICATION_CATALOG_FILTER`) — restricts which catalogs' proposals admins and stewards see. Default: all catalogs |
| `--profile NAME`                                                                             | one auth method                                         | Pre-configured Databricks CLI profile; otherwise uses `DATABRICKS_HOST` + `DATABRICKS_TOKEN` env vars                                                                    |
| `--lakebase-branch` / `--lakebase-database` / `--lakebase-host` / `--lakebase-endpoint-name` | all four, for an existing instance                      | Connection details for an existing Lakebase Autoscaling instance                                                                                                         |
| `--new-lakebase`                                                                             | alternative to the four above                           | Provision a brand-new Lakebase instance                                                                                                                                  |
| `-y`, `--yes`                                                                                | yes                                                     | Non-interactive mode; fail fast if any required value is missing                                                                                                         |


Run `./scripts/deploy.sh --help` for the full, authoritative flag list.

### Asset Permissions



#### App Admins

Admins are identified by the `ADMIN_EMAILS` environment variable on first login and managed in-app thereafter. The admin asset browser is built entirely from the classification proposals in `system.data_classification.results` (read by the service principal), so browsing assets, assigning stewards, and configuring tags require **no** per-admin Unity Catalog grants. The only admin action that runs **on behalf of the admin** via their forwarded access token (OBO) is **applying tags** — writing approved classifications back to Unity Catalog. That requires:


| Permission                                             | Purpose                                                                                |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| `USE CATALOG`, `USE SCHEMA` on target catalogs/schemas | Resolve the target column and read `information_schema.column_tags` when applying tags |
| `APPLY TAG` on target catalogs, schemas, or tables     | Write approved classification tags back to Unity Catalog                               |


> Admins do **not** need `SELECT` on monitored tables — inspecting live column sample values is a steward-only feature (see below). `SELECT` is only relevant if the same person also reviews proposals as a steward.



#### App Stewards

Stewards are assigned in-app by admins and require the following Unity Catalog permissions on their assigned tables. Like admins, UC metadata lookups run on behalf of the steward via OBO.


| Permission                                                          | Purpose                                                           |
| ------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `BROWSE` on assigned tables                                         | View table metadata                                               |
| [Optional] `USE CATALOG`, `USE SCHEMA`, `SELECT` on assigned tables | Run the live column sample query under the steward's own identity |


> A steward lacking `SELECT` (or the metadata grants) simply sees no sample values in the column detail view (the UI marks samples as unavailable rather than erroring). Grant these only if you want reviewers to inspect real column values while deciding.



### Build from Source and Deploy

Use this path when releasing a new version. The script builds the React frontend, packages the Python wheel, and then runs the same deployment steps as `deploy.sh`.

`install.sh` does **not** bump `pyproject.toml`'s version — Databricks Apps skips reinstalling a wheel whose version matches what's already installed on the app, so bump the version by hand before running this script whenever a code-only change needs to actually take effect.

#### Prerequisites

- [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html) on your PATH
- Python 3.11+ on your PATH
- Node.js 18+ with `npm` on your PATH
- [APX CLI](https://github.com/databricks-solutions/apx) on your PATH
- Permission to create a Databricks App
- Permission to create a Lakehouse Project or use an existing one



#### Steps

The installation script follows the same process as the deployment script, executing the build process before.

```bash
./scripts/install.sh
```



### Demo Deployment

Both `scripts/deploy.sh` and `scripts/install.sh` can optionally install a demo alongside the app. A single parametrized Databricks job (`data-classification-review-demo`) is deployed with the bundle and **only runs when you request a demo** — the default is **no demo**, so omitting the flags leaves a normal deployment unchanged.

There are three mutually-exclusive demo modes:

- `**single-catalog**` — creates demo schemas/tables with synthetic data inside one catalog you specify (created automatically if it doesn't already exist), and optionally enables **real** Unity Catalog data classification on it.
- `**multi-catalog**` — creates the 5 fixed `dc_demo_*` catalogs populated with synthetic data, and optionally enables **real** Unity Catalog data classification on them. For both catalog modes, the app keeps reading `system.data_classification.results`; the demo catalogs appear once classification completes.
- `**mock-results**` — skips real classification. It generates a results table you specify (creating the schema if missing), populates it from a committed snapshot, and points the app at it via `CLASSIFICATION_RESULTS_TABLE`. The app service principal is granted `SELECT` on that table automatically.



#### Flags


| Flag                           | Required                          | Description                                                                                                          |
| ------------------------------ | --------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `--demo MODE`                  | no (default `none`)               | Demo to install: `none`, `single-catalog`, `multi-catalog`, or `mock-results`                                        |
| `--demo-catalog NAME`          | yes, when `--demo single-catalog` | Catalog for the single-catalog demo — created automatically if it doesn't already exist                              |
| `--demo-enable-classification` | no (default off)                  | Enable the Data Classification feature on the demo catalog(s) — applies to `single-catalog` and `multi-catalog` only |
| `--demo-results-table NAME`    | yes, when `--demo mock-results`   | `catalog.schema.table` for the mock results table — the catalog must already exist; the schema is created if missing |


In the interactive path the script also prompts for the demo mode and its mode-specific options (catalog name and/or whether to enable classification, or the results table for `mock-results`).

#### Example

```bash
# Mock-results demo: build from source, deploy, and populate a mock table
./scripts/install.sh \
  --profile my-profile \
  --demo mock-results \
  --demo-results-table my_catalog.data_classification_demo.results \
  --warehouse-name "Serverless Starter Warehouse" \
  --admin-emails you@company.com \
  --new-lakebase \
  --yes
```

Swap `--demo mock-results --demo-results-table ...` for `--demo catalogs` to provision the demo catalogs with real classification instead. The same flags work with `./scripts/deploy.sh` when you already have pre-built artifacts.

## Project Structure

```
data-classification-review-app/
├── src/
│   └── data_classification_review_app/
│       ├── backend/
│       │   ├── app.py              # FastAPI entrypoint
│       │   ├── router.py           # Route registration
│       │   ├── models.py           # Pydantic request/response models
│       │   ├── routes/             # proposals, decisions, apply_tags, tables, stewards, tags, me
│       │   ├── clients/            # warehouse SQL client, UC SDK client
│       │   ├── core/               # Config, auth headers, SCIM, DI dependencies
│       │   ├── db/
│       │   │   ├── connection.py   # PGLite (local) / Lakebase (production)
│       │   │   ├── lifespan.py     # Startup/shutdown hooks
│       │   │   ├── seed.py         # Mock data seeding (USE_MOCK_DATA=true only)
│       │   │   └── migrations/     # SQL migration files (001–004)
│       │   └── mock/               # Static mock data for offline development
│       ├── _metadata.pyi           # Type stub — concrete file generated at build time
│       └── _version.pyi            # Type stub — concrete file generated at build time
├── frontend/
│   ├── src/
│   │   ├── steward/                # StewardInbox, ReviewDetail, ProposeColumnTagsSection, ReviewGuide
│   │   ├── admin/                  # AdminDashboard, AdminAssets, ApplyTags, AuditLog, StewardsAdminScreen, TagsAdminScreen
│   │   ├── shell/                  # AppShell, AppSideNav, AppTopBar
│   │   ├── components/             # Shared UI components
│   │   └── store/                  # api.ts, types.ts, useAppStore (Zustand)
│   └── public/fonts/               # Self-hosted font assets
├── demo/
│   ├── notebooks/                  # Demo job notebooks: single-catalog, multi-catalog, mock-results
│   └── data/                       # Committed classification_results.parquet snapshot (mock-results demo)
├── docs/
│   └── images/                     # README screenshots (Admin/Steward overview)
├── scripts/
│   ├── deploy.sh                   # Deploy from pre-built artifacts
│   └── install.sh                  # Build from source, then deploy
├── tests/                          # Pytest backend tests
├── app.yml                         # Databricks App manifest
├── databricks.yml                  # Databricks Asset Bundle configuration
└── pyproject.toml                  # Python project metadata
```



## Architecture

The app is deployed as a **Databricks App** backed by **Lakebase**:

- **Frontend**: React 18 + TypeScript, TanStack Query, Zustand, shadcn/ui + Tailwind CSS
- **Backend**: Python + FastAPI, Databricks SDK, APX framework
- **Database**: Lakebase Autoscaling (production)
- **Data source**: `system.data_classification.results` (Unity Catalog system table) and Unity Catalog APIs
- **Auth**: Databricks Apps OAuth
- **Deploy**: Databricks Asset Bundles (`databricks.yml`) + APX (`app.yml`)



## Contributing

Pull requests are welcome. For significant changes, please open an issue first to discuss what you would like to change.

- Follow [Conventional Commits](https://www.conventionalcommits.org/) for commit messages
- Run `apx dev check` before submitting (type-checks Python with `ty` and TypeScript with `tsc`)
- Add or update tests in `tests/` for backend changes



## License

@2026 Databricks, Inc. All rights reserved. The source in this repository is provided subject to the Databricks License [[https://databricks.com/db-license-source]](https://databricks.com/db-license-source]). All included or referenced third party libraries are subject to the licenses set forth below.


| library               | description                                            | license      | source                                                                                     |
| --------------------- | ------------------------------------------------------ | ------------ | ------------------------------------------------------------------------------------------ |
| @tanstack/react-query | Data fetching, caching, and state management for React | MIT          | [https://github.com/tanstack/query](https://github.com/tanstack/query)                     |
| databricks-sdk        | Databricks SDK for Python                              | Apache-2.0   | [https://pypi.org/project/databricks-sdk/](https://pypi.org/project/databricks-sdk/)       |
| fastapi               | Modern async web framework for APIs                    | MIT          | [https://pypi.org/project/fastapi/](https://pypi.org/project/fastapi/)                     |
| httpx                 | Async/sync HTTP client                                 | BSD-3-Clause | [https://pypi.org/project/httpx/](https://pypi.org/project/httpx/)                         |
| psycopg2-binary       | PostgreSQL database adapter for Python                 | LGPL-3.0     | [https://pypi.org/project/psycopg2-binary/](https://pypi.org/project/psycopg2-binary/)     |
| pydantic-settings     | Settings management with Pydantic                      | MIT          | [https://pypi.org/project/pydantic-settings/](https://pypi.org/project/pydantic-settings/) |
| python-dotenv         | Load environment variables from .env files             | BSD-3-Clause | [https://pypi.org/project/python-dotenv/](https://pypi.org/project/python-dotenv/)         |
| python-multipart      | Streaming multipart form data parser                   | Apache-2.0   | [https://pypi.org/project/python-multipart/](https://pypi.org/project/python-multipart/)   |
| react                 | Library for building user interfaces                   | MIT          | [https://github.com/facebook/react](https://github.com/facebook/react)                     |
| react-dom             | React DOM rendering                                    | MIT          | [https://github.com/facebook/react](https://github.com/facebook/react)                     |
| react-router-dom      | Declarative routing for React web applications         | MIT          | [https://github.com/remix-run/react-router](https://github.com/remix-run/react-router)     |
| uvicorn               | ASGI web server                                        | BSD-3-Clause | [https://pypi.org/project/uvicorn/](https://pypi.org/project/uvicorn/)                     |
| zustand               | Lightweight state management for React                 | MIT          | [https://github.com/pmndrs/zustand](https://github.com/pmndrs/zustand)                     |


