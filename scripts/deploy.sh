#!/usr/bin/env bash
# scripts/deploy.sh — deploy data-classification-review using pre-built artifacts
# Requires only the Databricks CLI — no npm or apx needed.
# Run scripts/install.sh instead if you need to build from source first.
set -euo pipefail

# ── formatting ──────────────────────────────────────────────────────────────
BOLD='\033[1m'; RESET='\033[0m'; GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'

print_step() { echo; echo -e "${CYAN}${BOLD}▶ $1${RESET}"; }
print_ok()   { echo -e "  ${GREEN}✓${RESET} $1"; }
die()        { echo -e "  ${RED}✗ $1${RESET}" >&2; exit 1; }
confirm()    { local prompt="$1"; local reply; read -r -p "  ${prompt} [y/n]: " reply; [[ "$reply" =~ ^[Yy]$ ]]; }

# Collect-and-continue permission handling: _perm_record notes a failed grant (echoing
# it inline) without exiting, so the deploy attempts every grant. report_permission_
# failures (defined below) then prints one aggregated summary and exits if any failed.
_perm_record() {
  PERM_FAILURES+=("$1")
  echo -e "  ${RED}✗ could not assign: $1${RESET}" >&2
}

# ── globals ──────────────────────────────────────────────────────────────────
PROFILE=""
CLI=()
WORKSPACE_HOST=""
WAREHOUSE_NAME=""
WAREHOUSE_ID=""
CATALOG_FILTER=""
ADMIN_EMAILS=""
LAKEBASE_ENDPOINT_NAME=""  # input — projects/<project>/branches/<branch>/endpoints/<endpoint>
LAKEBASE_LOGICAL_DB="databricks_postgres" # input — Postgres db name → LAKEBASE_DATABASE + CLASSIFICATION_SYNC_PG_DATABASE
# Derived from the two inputs above in _lakebase_resolve().
LAKEBASE_BRANCH=""
LAKEBASE_DATABASE=""
LAKEBASE_HOST=""
SP_ID=""
NEW_LAKEBASE=""
YES_MODE=""
SKIP_PERMS=""
PERM_FAILURES=()   # human-readable descriptions of grants that failed (collect-and-summarize)
DEMO_MODE=""
DEMO_CATALOG=""
DEMO_ENABLE_CLASSIFICATION=""
DEMO_RESULTS_TABLE=""
# Classification synced-table provisioning
CLASSIFICATION_CATALOG="data_classification_review_app"
CLASSIFICATION_SCHEMA="default"
CLASSIFICATION_VIEW="classification_results_v"
SYNCED_TABLE="classification_results"
SYNC_INTERVAL_HOURS="24"
# Derived in provision_classification_targets(), persisted in databricks.local.yml.
# The app — at startup, running as its SP — creates+owns the view, the synced table
# and the classification_sync refresh job (a single pipeline task); the script only
# creates the catalog/schema, grants the SP and waits for the app to finish. There is
# no deploy-time pipeline id — the app resolves it by synced-table name.
SYNCED_UC_NAME=""      # full UC name: catalog.schema.table  → CLASSIFICATION_SYNCED_TABLE_UC
SYNCED_PG_NAME=""      # Postgres landing name: schema.table  → CLASSIFICATION_SYNCED_TABLE
VIEW_UC=""             # full UC name of the deduped view    → CLASSIFICATION_VIEW_UC
SYNC_CRON=""           # quartz cron derived from SYNC_INTERVAL_HOURS
# Must match SYNC_JOB_NAME in backend/db/classification_job.py.
SYNC_JOB_NAME="data-classification-review classification sync"
# Postgres schema holding the app's own tables — must match APP_SCHEMA in
# backend/db/connection.py. Created and owned by the app SP.
APP_PG_SCHEMA="data_classification_review_app"
DEPLOYER=""            # deploying identity (email, or SP application id) — resolve_deployer()
# Optional one-off job running upgrade/copy_legacy_public_tables (copies the app data a
# 1.0.x install kept in Postgres `public`). Opt-in: --legacy-upgrade-job or the prompt.
LEGACY_UPGRADE_JOB=""
LEGACY_UPGRADE_JOB_KEY="data-classification-review-legacy-upgrade"
LEGACY_UPGRADE_JOB_NAME="Data Classification Review App - Migrate legacy schema from version 1.0.x"
APP_VERSION=""         # version of the pre-built wheel — check_prereqs()

# ── usage ────────────────────────────────────────────────────────────────────
usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Non-interactive deployment of the Data Classification Review app.
When all required flags are provided the script runs without any prompts.

Auth (pick one):
  --profile NAME              Databricks CLI profile (must already be configured)
                              Defaults to env vars DATABRICKS_HOST + DATABRICKS_TOKEN

Config:
  --catalog-filter LIST       Comma-separated catalog names to show (default: all)
  --admin-emails LIST         Comma-separated admin email addresses (required)
  --warehouse-name NAME       SQL warehouse name (required in non-interactive mode
                              unless --warehouse-id is given)
  --warehouse-id ID           SQL warehouse ID — skips listing all warehouses
                              (takes precedence over --warehouse-name)

Lakebase (pick one):
  --lakebase-endpoint-name N  Existing read-write endpoint
                              (e.g. projects/<project>/branches/<branch>/endpoints/primary);
                              branch, host and database path are looked up from it
  --new-lakebase              Provision a brand-new Lakebase instance
  --lakebase-database NAME    Postgres database on the endpoint's branch
                              (default: databricks_postgres)

Flags:
  --demo MODE                 Demo to install: none|single-catalog|multi-catalog|mock-results
                              (default: none)
  --demo-catalog NAME         Catalog for the single-catalog demo — created if it
                              doesn't exist (required when --demo single-catalog)
  --demo-enable-classification  Enable the Data Classification feature on the demo
                              catalog(s) (single-catalog and multi-catalog only;
                              default: off)
  --demo-results-table NAME   catalog.schema.table for the mock results table
                              (required when --demo mock-results; the catalog
                              must already exist — the schema is created if missing)

Classification synced table (provisioned at install; sensible defaults):
  --classification-catalog N  UC catalog for the classification view + synced
                              table (default: data_classification_review_app;
                              created if missing)
  --classification-schema N   UC schema inside that catalog
                              (default: default; created if missing)
  --classification-view NAME  View name with the QUALIFY dedup over
                              system.data_classification.results
                              (default: classification_results_v)
  --synced-table NAME         Synced (Lakebase) table name that the app reads
                              (default: classification_results)
  --sync-interval-hours N     Sync cadence in hours; maps to the sync job cron
                              (default: 24 → daily)
  --skip-permission-assignment  Skip all grant/permission-assignment steps. Use when you
                              lack the rights and the grants have already been applied
                              out of band; the deploy still starts the app, which
                              provisions the view, synced table and sync job (it
                              assumes those permissions are in place).
  --legacy-upgrade-job        Also create a manual, one-click job that copies the app
                              data a 1.0.x install kept in Postgres \`public\` into
                              the current schema (runs as you; prefilled from this
                              deploy). Only needed when upgrading from 1.0.x; a later
                              deploy without it removes the job. Interactive installs
                              ask instead.
  -y, --yes                   Non-interactive mode; fail if required params are missing
  -h, --help                  Show this help

Examples:
  # Fully non-interactive (env-var auth, existing Lakebase)
  export DATABRICKS_HOST=https://my.azuredatabricks.net
  export DATABRICKS_TOKEN=dapi...
  $(basename "$0") --admin-emails me@co.com --warehouse-name "Shared" \\
    --lakebase-endpoint-name "projects/x/branches/production/endpoints/primary" \\
    --lakebase-database "my_database" \\
    --yes

  # Fully non-interactive (profile auth, new Lakebase)
  $(basename "$0") --profile myprofile --admin-emails me@co.com \\
    --warehouse-name "Shared" --new-lakebase --yes
EOF
}

# ── arg parsing ───────────────────────────────────────────────────────────────
parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile)                PROFILE="$2";                shift 2 ;;
      --catalog-filter)         CATALOG_FILTER="$2";         shift 2 ;;
      --admin-emails)           ADMIN_EMAILS="$2";           shift 2 ;;
      --warehouse-name)         WAREHOUSE_NAME="$2";         shift 2 ;;
      --warehouse-id)           WAREHOUSE_ID="$2";           shift 2 ;;
      --lakebase-endpoint-name) LAKEBASE_ENDPOINT_NAME="$2"; shift 2 ;;
      --lakebase-database)      LAKEBASE_LOGICAL_DB="$2";    shift 2 ;;
      --new-lakebase)           NEW_LAKEBASE=1;              shift ;;
      --demo)                   DEMO_MODE="$2";              shift 2 ;;
      --demo-catalog)           DEMO_CATALOG="$2";           shift 2 ;;
      --demo-enable-classification) DEMO_ENABLE_CLASSIFICATION=1; shift ;;
      --demo-results-table)     DEMO_RESULTS_TABLE="$2";     shift 2 ;;
      --classification-catalog) CLASSIFICATION_CATALOG="$2"; shift 2 ;;
      --classification-schema)  CLASSIFICATION_SCHEMA="$2";  shift 2 ;;
      --classification-view)    CLASSIFICATION_VIEW="$2";    shift 2 ;;
      --synced-table)           SYNCED_TABLE="$2";           shift 2 ;;
      --sync-interval-hours)    SYNC_INTERVAL_HOURS="$2";    shift 2 ;;
      --skip-permission-assignment) SKIP_PERMS=1;            shift ;;
      --legacy-upgrade-job)     LEGACY_UPGRADE_JOB=1;        shift ;;
      -y|--yes)                 YES_MODE=1;                  shift ;;
      -h|--help)                usage; exit 0 ;;
      *) die "Unknown option: $1. Run with --help for usage." ;;
    esac
  done
}

# ── prerequisites ────────────────────────────────────────────────────────────
check_prereqs() {
  print_step "Checking prerequisites"
  command -v databricks >/dev/null 2>&1 \
    || die "databricks CLI not found. Install from https://docs.databricks.com/dev-tools/cli/install.html"
  [[ -d .build ]] \
    || die ".build/ directory not found — run scripts/install.sh to build from source first"
  local whl
  whl=$(ls .build/*.whl 2>/dev/null | head -1)
  [[ -n "$whl" ]] \
    || die "No wheel found in .build/ — run scripts/install.sh to build from source first"
  # data_classification_review_app-<version>-py3-none-any.whl → <version>
  APP_VERSION=$(basename "$whl" | cut -d- -f2)
  print_ok "databricks CLI found"
  print_ok "Pre-built artifact: $(basename "$whl")"
}

# ── auth ─────────────────────────────────────────────────────────────────────
auth_login() {
  print_step "Authentication"

  # Non-interactive path 1: env vars already exported
  if [[ -n "${DATABRICKS_HOST:-}" && -n "${DATABRICKS_TOKEN:-}" ]]; then
    WORKSPACE_HOST="$DATABRICKS_HOST"
    CLI=()
    print_ok "Using environment credentials → $WORKSPACE_HOST"
    return
  fi

  # Non-interactive path 2: --profile provided (must already be configured)
  if [[ -n "$PROFILE" ]]; then
    local existing_host
    existing_host=$(databricks auth env --profile "$PROFILE" 2>/dev/null \
      | grep DATABRICKS_HOST | cut -d= -f2 | tr -d '"' || true)
    [[ -n "$existing_host" ]] \
      || die "Profile '$PROFILE' has no DATABRICKS_HOST. Run 'databricks auth login --profile $PROFILE' first."
    WORKSPACE_HOST="$existing_host"
    CLI=(--profile "$PROFILE")
    print_ok "Using profile '$PROFILE' → $WORKSPACE_HOST"
    return
  fi

  # Interactive path
  echo "  How would you like to authenticate?"
  echo "    1) Environment variables — DATABRICKS_HOST + DATABRICKS_TOKEN already set"
  echo "       (use this on a Databricks cluster web terminal or CI environment)"
  echo "    2) Interactive login — databricks auth login opens a browser"
  read -r -p "  Choice [1/2]: " auth_choice

  if [[ "$auth_choice" == "1" ]]; then
    [[ -n "${DATABRICKS_HOST:-}" ]] \
      || die "DATABRICKS_HOST is not set — export it before running this script"
    [[ -n "${DATABRICKS_TOKEN:-}" ]] \
      || die "DATABRICKS_TOKEN is not set — export it before running this script"
    WORKSPACE_HOST="$DATABRICKS_HOST"
    CLI=()
    print_ok "Using environment credentials → $WORKSPACE_HOST"
  else
    read -r -p "  Databricks CLI profile name (default: DEFAULT): " PROFILE
    PROFILE="${PROFILE:-DEFAULT}"

    local existing_host
    existing_host=$(databricks auth env --profile "$PROFILE" 2>/dev/null \
      | grep DATABRICKS_HOST | cut -d= -f2 | tr -d '"' || true)

    local host_flag=""
    if [[ -z "$existing_host" ]]; then
      read -r -p "  Workspace URL (e.g. https://your-workspace.cloud.databricks.com): " host_flag
      [[ -n "$host_flag" ]] || die "Workspace URL is required for a new profile"
      host_flag="--host $host_flag"
    fi

    # shellcheck disable=SC2086
    databricks auth login --profile "$PROFILE" $host_flag \
      || die "Authentication failed for profile '$PROFILE'"

    WORKSPACE_HOST=$(databricks auth env --profile "$PROFILE" 2>/dev/null \
      | grep DATABRICKS_HOST | cut -d= -f2 | tr -d '"' || true)
    [[ -n "$WORKSPACE_HOST" ]] \
      || die "Profile '$PROFILE' has no DATABRICKS_HOST after login"
    CLI=(--profile "$PROFILE")
    print_ok "Authenticated → $WORKSPACE_HOST"
  fi
}

# ── config ───────────────────────────────────────────────────────────────────
collect_config() {
  print_step "Configuration"

  if [[ -z "$CATALOG_FILTER" && -z "$YES_MODE" ]]; then
    read -r -p "  Catalog filter (comma-separated catalog names, leave empty to show all): " CATALOG_FILTER
  fi

  # Where to host the classification view + Lakebase synced table. Interactive
  # only — non-interactive (--yes) mode keeps the flag/default values as-is.
  # Prompts pre-fill the current value (default or --classification-* flag), so
  # pressing enter keeps it.
  if [[ -z "$YES_MODE" ]]; then
    local _reply
    read -r -p "  Classification catalog to host the view + synced table [${CLASSIFICATION_CATALOG}]: " _reply
    CLASSIFICATION_CATALOG="${_reply:-$CLASSIFICATION_CATALOG}"
    read -r -p "  Classification schema [${CLASSIFICATION_SCHEMA}]: " _reply
    CLASSIFICATION_SCHEMA="${_reply:-$CLASSIFICATION_SCHEMA}"
  fi
  [[ -n "$CLASSIFICATION_CATALOG" && -n "$CLASSIFICATION_SCHEMA" ]] \
    || die "Classification catalog and schema cannot be empty"

  # Permission assignment — interactive opt-out. Assigning the UC/Lakebase grants
  # needs admin-level rights; if you lack them, answer no and have an
  # admin apply them (the deploy then assumes they are already in place). The
  # --skip-permission-assignment flag sets this non-interactively.
  if [[ -z "$SKIP_PERMS" && -z "$YES_MODE" ]]; then
    if confirm "Assign the required grants/permissions during this deploy? (No = an admin applies them separately)"; then
      print_ok "Permissions    : assigned during deploy"
    else
      SKIP_PERMS=1
      print_ok "Permissions    : skipped (assumed already assigned)"
    fi
  fi

  # Legacy-data migration job — interactive opt-in (default no); --legacy-upgrade-job
  # sets it non-interactively. Only useful when upgrading an install from 1.0.x.
  if [[ -z "$LEGACY_UPGRADE_JOB" && -z "$YES_MODE" ]]; then
    if confirm "Upgrading from 1.0.x? Create a job to migrate its data from the legacy Postgres schema (public)?"; then
      LEGACY_UPGRADE_JOB=1
    fi
  fi
  if [[ -n "$LEGACY_UPGRADE_JOB" ]]; then
    print_ok "Legacy upgrade : job \"${LEGACY_UPGRADE_JOB_NAME}\" will be created"
  fi

  if [[ -z "$ADMIN_EMAILS" ]]; then
    [[ -n "$YES_MODE" ]] && die "--admin-emails is required in non-interactive mode"
    read -r -p "  Admin emails (comma-separated, e.g. you@company.com): " ADMIN_EMAILS
  fi
  [[ -n "$ADMIN_EMAILS" ]] || die "ADMIN_EMAILS cannot be empty"

  if [[ -n "$WAREHOUSE_ID" ]]; then
    WAREHOUSE_NAME=$(databricks warehouses get "$WAREHOUSE_ID" --output json "${CLI[@]}" \
      | python3 -c 'import json,sys; print(json.load(sys.stdin)["name"])' 2>/dev/null) \
      || die "Warehouse ID '$WAREHOUSE_ID' not found"
    print_ok "Catalog filter : ${CATALOG_FILTER:-(all)}"
    print_ok "Admin emails   : $ADMIN_EMAILS"
    print_ok "Classification : ${CLASSIFICATION_CATALOG}.${CLASSIFICATION_SCHEMA}"
    print_ok "Warehouse      : $WAREHOUSE_NAME (ID: $WAREHOUSE_ID, skipped full listing)"
  else
    echo "  Fetching available SQL warehouses..."
    local WAREHOUSE_TEXT
    WAREHOUSE_TEXT=$(databricks warehouses list --output text "${CLI[@]}" | grep -E '^[0-9a-f]{16}' || true)

    local WAREHOUSE_NAMES=()
    local WAREHOUSE_IDS=()
    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      WAREHOUSE_IDS+=("$(echo "$line" | awk '{print $1}')")
      WAREHOUSE_NAMES+=("$(echo "$line" | awk '{for(i=2;i<=NF-2;i++) printf "%s%s",$i,(i<NF-2?" ":"\n")}')")
    done <<< "$WAREHOUSE_TEXT"

    [[ ${#WAREHOUSE_NAMES[@]} -gt 0 ]] || die "No SQL warehouses found in this workspace"

    if [[ -n "$WAREHOUSE_NAME" ]]; then
      # Match by name — find the corresponding ID
      local found=0
      local i
      for i in "${!WAREHOUSE_NAMES[@]}"; do
        if [[ "${WAREHOUSE_NAMES[$i]}" == "$WAREHOUSE_NAME" ]]; then
          WAREHOUSE_ID="${WAREHOUSE_IDS[$i]}"
          found=1
          break
        fi
      done
      [[ $found -eq 1 ]] \
        || die "Warehouse '$WAREHOUSE_NAME' not found. Available: $(IFS=', '; echo "${WAREHOUSE_NAMES[*]}")"
    else
      [[ -n "$YES_MODE" ]] && die "--warehouse-name or --warehouse-id is required in non-interactive mode"

      echo "  Available warehouses:"
      local i
      for i in "${!WAREHOUSE_NAMES[@]}"; do
        echo "    $((i+1))) ${WAREHOUSE_NAMES[$i]}"
      done

      local sel
      read -r -p "  Select warehouse number: " sel
      local idx=$((sel-1))
      [[ $idx -ge 0 && $idx -lt ${#WAREHOUSE_NAMES[@]} ]] || die "Invalid selection: $sel"

      WAREHOUSE_NAME="${WAREHOUSE_NAMES[$idx]}"
      WAREHOUSE_ID="${WAREHOUSE_IDS[$idx]}"
    fi

    print_ok "Catalog filter : ${CATALOG_FILTER:-(all)}"
    print_ok "Admin emails   : $ADMIN_EMAILS"
    print_ok "Classification : ${CLASSIFICATION_CATALOG}.${CLASSIFICATION_SCHEMA}"
    print_ok "Warehouse      : $WAREHOUSE_NAME (ID: $WAREHOUSE_ID)"
  fi

}

# ── demo selection ───────────────────────────────────────────────────────────
collect_demo_config() {
  print_step "Demo selection"

  if [[ -z "$DEMO_MODE" ]]; then
    if [[ -n "$YES_MODE" ]]; then
      DEMO_MODE="none"
    else
      echo "  Install a demo?"
      echo "    1) none            (default)"
      echo "    2) single-catalog  — create demo data in one catalog you choose, optionally enable classification"
      echo "    3) multi-catalog   — create 5 dc_demo_* catalogs, optionally enable classification"
      echo "    4) mock-results    — generate & populate a mock results table"
      read -r -p "  Choice [1/2/3/4] (default 1): " demo_choice
      case "${demo_choice:-1}" in
        1) DEMO_MODE="none" ;;
        2) DEMO_MODE="single-catalog" ;;
        3) DEMO_MODE="multi-catalog" ;;
        4) DEMO_MODE="mock-results" ;;
        *) die "Invalid demo choice: $demo_choice" ;;
      esac
    fi
  fi

  case "$DEMO_MODE" in
    none|single-catalog|multi-catalog|mock-results) ;;
    *) die "Invalid --demo value: $DEMO_MODE (expected none|single-catalog|multi-catalog|mock-results)" ;;
  esac

  if [[ "$DEMO_MODE" == "single-catalog" && -z "$DEMO_CATALOG" ]]; then
    [[ -n "$YES_MODE" ]] && die "--demo-catalog is required with --demo single-catalog"
    read -r -p "  Demo catalog (created automatically if it doesn't exist): " DEMO_CATALOG
    [[ -n "$DEMO_CATALOG" ]] || die "Demo catalog name cannot be empty"
  fi

  if [[ "$DEMO_MODE" == "single-catalog" || "$DEMO_MODE" == "multi-catalog" ]]; then
    if [[ -z "$DEMO_ENABLE_CLASSIFICATION" && -z "$YES_MODE" ]]; then
      confirm "Enable the Data Classification feature on the demo catalog(s)?" \
        && DEMO_ENABLE_CLASSIFICATION=1
    fi
  fi

  if [[ "$DEMO_MODE" == "mock-results" && -z "$DEMO_RESULTS_TABLE" ]]; then
    [[ -n "$YES_MODE" ]] && die "--demo-results-table is required with --demo mock-results"
    read -r -p "  Mock results table (catalog.schema.table, catalog must already exist): " DEMO_RESULTS_TABLE
  fi
  if [[ "$DEMO_MODE" == "mock-results" ]]; then
    [[ "$DEMO_RESULTS_TABLE" =~ ^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+){2}$ ]] \
      || die "--demo-results-table must be catalog.schema.table, got: $DEMO_RESULTS_TABLE"
  fi

  print_ok "Demo           : ${DEMO_MODE}${DEMO_CATALOG:+ ($DEMO_CATALOG)}${DEMO_RESULTS_TABLE:+ ($DEMO_RESULTS_TABLE)}"
  if [[ "$DEMO_MODE" == "single-catalog" || "$DEMO_MODE" == "multi-catalog" ]]; then
    print_ok "Classification : $([[ -n "$DEMO_ENABLE_CLASSIFICATION" ]] && echo enabled || echo "not enabled")"
  fi
}

# ── lakebase ─────────────────────────────────────────────────────────────────
_lakebase_new() {
  local project_id="data-classification-review-app"
  local branch_id="production"
  local endpoint_id="primary"

  echo "  Creating Lakebase project (may take a minute)..."
  if ! databricks postgres create-project "$project_id" \
      "${CLI[@]}" \
      --json '{"display_name": "Data Classification Review"}' 2>/dev/null; then
    print_ok "Project already exists — reusing"
  else
    print_ok "Project created: projects/$project_id"
  fi

  echo "  Creating production branch — PostgreSQL 17 (may take several minutes)..."
  if ! databricks postgres create-branch "projects/$project_id" "$branch_id" \
      "${CLI[@]}" \
      --json '{"spec": {"engine_version": "PG_17"}}' 2>/dev/null; then
    print_ok "Branch already exists — reusing"
  else
    print_ok "Branch created: projects/$project_id/branches/$branch_id"
  fi

  echo "  Creating primary endpoint..."
  LAKEBASE_ENDPOINT_NAME="projects/$project_id/branches/$branch_id/endpoints/$endpoint_id"
  databricks postgres create-endpoint \
    "projects/$project_id/branches/$branch_id" "$endpoint_id" \
    "${CLI[@]}" >/dev/null 2>&1 || true

  # Wait until the endpoint has a host; _lakebase_resolve reads it afterwards.
  local host="" i=0
  while [[ -z "$host" && $i -lt 12 ]]; do
    host=$(databricks postgres get-endpoint "$LAKEBASE_ENDPOINT_NAME" \
      --output json "${CLI[@]}" 2>/dev/null \
      | grep '"host"' | head -1 | cut -d'"' -f4 || true)
    [[ -n "$host" ]] || { sleep 5; i=$((i+1)); }
  done
  [[ -n "$host" ]] || die "Timed out waiting for endpoint host"
}

# Everything else follows from the endpoint name + Postgres database name: the branch
# is the endpoint's parent, the host and type come from the endpoint, and the database
# path from the branch's databases. The path's id (…/databases/<id>) and the Postgres
# name are independent — even the default database is id "databricks-postgres",
# Postgres name "databricks_postgres" — but a Postgres name is unique on a branch.
_lakebase_resolve() {
  [[ "$LAKEBASE_ENDPOINT_NAME" =~ ^projects/[^/]+/branches/[^/]+/endpoints/[^/]+$ ]] \
    || die "Endpoint name must look like projects/<project>/branches/<branch>/endpoints/<endpoint>, got: ${LAKEBASE_ENDPOINT_NAME}"
  LAKEBASE_BRANCH="${LAKEBASE_ENDPOINT_NAME%/endpoints/*}"

  local ep_json ep_type
  ep_json=$(databricks postgres get-endpoint "$LAKEBASE_ENDPOINT_NAME" --output json "${CLI[@]}") \
    || die "Could not read Lakebase endpoint $LAKEBASE_ENDPOINT_NAME (see error above)"
  ep_type=$(echo "$ep_json" | python3 -c '
import json, sys
print((json.load(sys.stdin).get("status") or {}).get("endpoint_type") or "")')
  [[ "$ep_type" == "ENDPOINT_TYPE_READ_WRITE" ]] \
    || die "Endpoint $LAKEBASE_ENDPOINT_NAME is ${ep_type:-of unknown type}; the app needs a read-write endpoint"
  LAKEBASE_HOST=$(echo "$ep_json" | python3 -c '
import json, sys
print(((json.load(sys.stdin).get("status") or {}).get("hosts") or {}).get("host") or "")')
  [[ -n "$LAKEBASE_HOST" ]] || die "Endpoint $LAKEBASE_ENDPOINT_NAME has no host"

  # Two lines: the matching database path (empty if none), then the available names.
  local dbs_json match available
  dbs_json=$(databricks postgres list-databases "$LAKEBASE_BRANCH" --output json "${CLI[@]}") \
    || die "Could not list the databases of $LAKEBASE_BRANCH (see error above)"
  { read -r match; read -r available; } < <(echo "$dbs_json" | python3 -c '
import json, sys
dbs = json.load(sys.stdin)
if isinstance(dbs, dict):
    dbs = dbs.get("databases") or []
def pg(d):
    return ((d.get("status") or {}).get("postgres_database")
            or (d.get("spec") or {}).get("postgres_database") or "")
print(next((d["name"] for d in dbs if pg(d) == sys.argv[1]), ""))
print(", ".join(sorted(filter(None, map(pg, dbs)))) or "none")' "$LAKEBASE_LOGICAL_DB") || true
  [[ -n "$match" ]] \
    || die "No database \"$LAKEBASE_LOGICAL_DB\" on $LAKEBASE_BRANCH. Available: $available"
  LAKEBASE_DATABASE="$match"

  print_ok "Endpoint host: $LAKEBASE_HOST"
  print_ok "Database: $LAKEBASE_LOGICAL_DB ($LAKEBASE_DATABASE)"
}

setup_lakebase() {
  print_step "Lakebase setup"

  if [[ -n "$LAKEBASE_ENDPOINT_NAME" ]]; then
    :  # existing instance from --lakebase-endpoint-name
  elif [[ -n "$NEW_LAKEBASE" ]]; then
    _lakebase_new
  elif [[ -n "$YES_MODE" ]]; then
    die "Non-interactive mode requires either --lakebase-endpoint-name (existing instance) or --new-lakebase"
  elif confirm "Do you have an existing Lakebase Autoscaling instance?"; then
    read -r -p "  Endpoint name (e.g. projects/<project>/branches/<branch>/endpoints/primary): " LAKEBASE_ENDPOINT_NAME
    [[ -n "$LAKEBASE_ENDPOINT_NAME" ]] || die "Endpoint name is required"
    local _reply
    read -r -p "  Database [${LAKEBASE_LOGICAL_DB}]: " _reply
    LAKEBASE_LOGICAL_DB="${_reply:-$LAKEBASE_LOGICAL_DB}"
  else
    _lakebase_new
  fi

  _lakebase_resolve
}

# ── local files ───────────────────────────────────────────────────────────────
# Regenerates databricks.local.yml before the (single) bundle deploy.
#
# All app-consumed values are PERSISTED here as variables (not passed via --var),
# so every bundle command — deploy AND run — resolves the same values.
# `databricks bundle run <app>` re-applies the app's config.env, and a var left at
# its empty default would render an env entry with no value ("Must specify
# environment variable source using either value or valueFrom").
write_local_files() {
  print_step "Writing local configuration"

  local resources_body=""
  if [[ -n "$CATALOG_FILTER" ]]; then
    resources_body="
      apps:
        data-classification-review-app:
          config:
            env:
              - name: CLASSIFICATION_CATALOG_FILTER
                value: \"${CATALOG_FILTER}\""
  fi
  # Opt-in legacy-data migration job: one serverless notebook task, parameters
  # prefilled from this deploy (bundle variables), run manually — never scheduled.
  # Runs as its owner, the deployer. A plain "Run now" copies for real (the copy is
  # idempotent and keeps the old tables); dry_run/drop_legacy can be overridden.
  if [[ -n "$LEGACY_UPGRADE_JOB" ]]; then
    resources_body="${resources_body}
      jobs:
        ${LEGACY_UPGRADE_JOB_KEY}:
          name: \"${LEGACY_UPGRADE_JOB_NAME}\"
          parameters:
            - name: endpoint
              default: \"\${var.lakebase_endpoint_name}\"
            - name: database
              default: \"\${var.lakebase_logical_db}\"
            - name: source_schema
              default: \"public\"
            - name: target_schema
              default: \"${APP_PG_SCHEMA}\"
            - name: dry_run
              default: \"false\"
            - name: drop_legacy
              default: \"false\"
          tasks:
            - task_key: copy_legacy_public_tables
              notebook_task:
                notebook_path: \${workspace.file_path}/upgrade/copy_legacy_public_tables
                base_parameters:
                  endpoint: \"{{job.parameters.endpoint}}\"
                  database: \"{{job.parameters.database}}\"
                  source_schema: \"{{job.parameters.source_schema}}\"
                  target_schema: \"{{job.parameters.target_schema}}\"
                  dry_run: \"{{job.parameters.dry_run}}\"
                  drop_legacy: \"{{job.parameters.drop_legacy}}\""
  fi
  local resources_block=""
  [[ -n "$resources_body" ]] && resources_block="    resources:${resources_body}"

  # Who gets CAN_MANAGE on the sync job the app creates: the deployer (so this
  # script can trigger its first run) plus the app admins.
  local managers="$DEPLOYER" admin admins=()
  IFS=',' read -r -a admins <<< "$ADMIN_EMAILS"
  for admin in "${admins[@]}"; do
    admin="${admin// /}"
    if [[ -n "$admin" && ",${managers}," != *",${admin},"* ]]; then
      managers="${managers},${admin}"
    fi
  done

  local results_table_block=""
  if [[ "$DEMO_MODE" == "mock-results" ]]; then
    results_table_block="      classification_results_table: \"${DEMO_RESULTS_TABLE}\""
  fi

  cat > databricks.local.yml <<YAML
# Auto-generated by scripts/deploy.sh — do not commit
targets:
  prod:
    variables:
      warehouse_id:
        lookup:
          warehouse: "${WAREHOUSE_NAME}"
      lakebase_branch: "${LAKEBASE_BRANCH}"
      lakebase_database: "${LAKEBASE_DATABASE}"
      lakebase_host: "${LAKEBASE_HOST}"
      lakebase_endpoint_name: "${LAKEBASE_ENDPOINT_NAME}"
      lakebase_logical_db: "${LAKEBASE_LOGICAL_DB}"
      admin_emails: "${ADMIN_EMAILS}"
      synced_uc_name: "${SYNCED_UC_NAME}"
      synced_pg_name: "${SYNCED_PG_NAME}"
      classification_view_uc: "${VIEW_UC}"
      sync_cron: "${SYNC_CRON}"
      sync_job_managers: "${managers}"
${results_table_block}
${resources_block}
YAML
  print_ok "databricks.local.yml written"

  # Widget defaults for the upgrade notebook (upgrade/copy_legacy_public_tables), so a
  # manual run is prefilled for this installation. Git-ignored; the bundle syncs it
  # next to the notebook (sync.include: upgrade).
  if [[ -d upgrade ]]; then
    python3 - "$LAKEBASE_ENDPOINT_NAME" "$LAKEBASE_LOGICAL_DB" "$APP_PG_SCHEMA" \
      > upgrade/install_defaults.json <<'PY'
import json, sys
endpoint, database, target_schema = sys.argv[1:4]
print(json.dumps({"endpoint": endpoint, "database": database,
                  "source_schema": "public", "target_schema": target_schema}, indent=2))
PY
    print_ok "upgrade/install_defaults.json written"
  fi

  if ! grep -q "databricks.local.yml" databricks.yml; then
    printf '\ninclude:\n  - databricks.local.yml\n' >> databricks.yml
    print_ok "databricks.yml patched with include: block"
  else
    print_ok "databricks.yml already includes databricks.local.yml — skipped"
  fi

  if ! grep -q "^databricks.local.yml" .gitignore 2>/dev/null; then
    printf '\ndatabricks.local.yml\n' >> .gitignore
    print_ok ".gitignore updated"
  else
    print_ok ".gitignore already excludes databricks.local.yml — skipped"
  fi
}

# ── classification target provisioning ────────────────────────────────────────
# Maps --sync-interval-hours to a quartz cron for the DAB sync job.
# Note: intervals that don't divide 24 evenly (e.g. 5, 7, 9) produce an
# approximate daily cadence — the hour field resets at midnight each day, so
# the last partial interval before midnight is truncated.
_derive_sync_cron() {
  if [[ "${SYNC_INTERVAL_HOURS}" -ge 24 ]]; then
    SYNC_CRON="0 0 0 */1 * ?"                      # daily at 00:00 UTC
  else
    SYNC_CRON="0 0 */${SYNC_INTERVAL_HOURS} * * ?" # every N hours
  fi
}

# Create the catalog/schema and derive the names the app + bundle need. The view
# and synced table themselves are created by the app at startup — running as the
# app service principal — so the view is SP-owned (a UC view executes with its
# owner's privileges, which is what lets the SNAPSHOT read the source system table
# regardless of who ran this install).
provision_classification_targets() {
  print_step "Preparing classification catalog + schema"

  local cat="$CLASSIFICATION_CATALOG" sch="$CLASSIFICATION_SCHEMA"
  VIEW_UC="${cat}.${sch}.${CLASSIFICATION_VIEW}"       # → CLASSIFICATION_VIEW_UC
  SYNCED_UC_NAME="${cat}.${sch}.${SYNCED_TABLE}"       # → CLASSIFICATION_SYNCED_TABLE_UC
  SYNCED_PG_NAME="${sch}.${SYNCED_TABLE}"              # → CLASSIFICATION_SYNCED_TABLE

  # Catalog + schema — create-if-missing (idempotent).
  databricks catalogs get "$cat" "${CLI[@]}" >/dev/null 2>&1 \
    || databricks catalogs create "$cat" "${CLI[@]}" >/dev/null \
    || die "Failed to create catalog $cat"
  databricks schemas get "${cat}.${sch}" "${CLI[@]}" >/dev/null 2>&1 \
    || databricks schemas create "$sch" "$cat" "${CLI[@]}" >/dev/null \
    || die "Failed to create schema ${cat}.${sch}"
  print_ok "Catalog/schema ready: ${cat}.${sch}"

  _derive_sync_cron
  print_ok "View target    : ${VIEW_UC} (created by the app as the SP)"
  print_ok "Synced table   : ${SYNCED_UC_NAME} (Postgres: ${SYNCED_PG_NAME})"
  print_ok "Sync schedule  : every ${SYNC_INTERVAL_HOURS}h (cron: ${SYNC_CRON})"
}

# ── deploy ───────────────────────────────────────────────────────────────────
# All values come from databricks.local.yml (written by write_local_files), so no
# --var is needed and every bundle command resolves the same values. No pipeline id
# is wired — the app and the sync job resolve it by synced-table name.
# $1 = optional label for logging (e.g. "sync paused").
_bundle_deploy() {
  local label="${1:-}"

  print_step "Deploying bundle${label:+ (${label})}"

  rm -rf .databricks/bundle/prod/
  print_ok "Local bundle cache cleared"

  echo "  Running: databricks bundle deploy -t prod ${CLI[*]}"
  echo "  (Uploading pre-built artifacts — may take a few minutes)"
  databricks bundle deploy -t prod --force-lock "${CLI[@]}" \
    || die "bundle deploy failed — check output above"
  print_ok "Bundle deployed${label:+ (${label})}"
}

# The deploying identity. A service-principal deployer (e.g. CI) reports its
# application id as userName. Granted CAN_MANAGE on the sync job the app creates, so
# this script (and the deployer) can see and run it.
resolve_deployer() {
  DEPLOYER=$(databricks current-user me "${CLI[@]}" --output json \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['userName'])" 2>/dev/null) \
    || die "Could not resolve the deploying identity (databricks current-user me)"
  [[ -n "$DEPLOYER" ]] || die "Could not resolve the deploying identity (databricks current-user me)"
  print_ok "Deploying as  : ${DEPLOYER}"
}

discover_sp_id() {
  print_step "Discovering app service principal"
  SP_ID=$(databricks apps get "data-classification-review-app" \
    "${CLI[@]}" --output json \
    | grep '"service_principal_client_id"' \
    | cut -d'"' -f4)
  [[ -n "$SP_ID" ]] \
    || die "Could not find service_principal_client_id — was the app created by bundle deploy?"
  print_ok "Service principal client ID: $SP_ID"
}

# The complete set of grants the deploy needs, with copy-pasteable commands. Printed
# both by the skip-mode notice and by the failure summary (report_permission_failures).
# Kept in sync with the README section "Deployment prerequisites (permissions)".
print_required_permissions() {
  local project_name="${LAKEBASE_BRANCH#projects/}"; project_name="${project_name%%/*}"
  echo    "  Service principal (app): ${SP_ID}"
  if [[ "$DEMO_MODE" == "mock-results" ]]; then
    local cat sch; cat="${DEMO_RESULTS_TABLE%%.*}"; sch="$(echo "$DEMO_RESULTS_TABLE" | cut -d. -f2)"
    echo  "  1) SELECT on the demo results table — its owner:"
    echo  "       GRANT USE CATALOG ON CATALOG \`${cat}\` TO \`${SP_ID}\`;"
    echo  "       GRANT USE SCHEMA ON SCHEMA \`${cat}\`.\`${sch}\` TO \`${SP_ID}\`;"
    echo  "       GRANT SELECT ON TABLE ${DEMO_RESULTS_TABLE} TO \`${SP_ID}\`;"
  else
    echo  "  1) SELECT on the classification source — account/metastore admin:"
    echo  "       GRANT USE CATALOG ON CATALOG system TO \`${SP_ID}\`;"
    echo  "       GRANT SELECT ON TABLE system.data_classification.results TO \`${SP_ID}\`;"
  fi
  echo    "  2) Create + own in the target schema — owner of ${CLASSIFICATION_CATALOG}:"
  echo    "       GRANT USE CATALOG ON CATALOG \`${CLASSIFICATION_CATALOG}\` TO \`${SP_ID}\`;"
  echo    "       GRANT ALL PRIVILEGES ON SCHEMA \`${CLASSIFICATION_CATALOG}\`.\`${CLASSIFICATION_SCHEMA}\` TO \`${SP_ID}\`;"
  echo    "  3) 'Can Use' on the Lakebase project — project manager:"
  echo    "       databricks api patch /api/2.0/permissions/database-projects/${project_name} \\"
  echo    "         --json '{\"access_control_list\":[{\"service_principal_name\":\"${SP_ID}\",\"permission_level\":\"CAN_USE\"}]}'"
  echo    "  (No Postgres superuser: the app creates and owns its own schema"
  echo    "   '${APP_PG_SCHEMA}' with the CREATE-on-database right its Lakebase resource grants.)"
}

# After all grant steps have been attempted, print an aggregated summary of the ones
# that failed (if any) plus the full required set + README pointer, then exit. Called
# once, before the app starts (and provisions), so nothing downstream runs against
# missing permissions.
report_permission_failures() {
  [[ ${#PERM_FAILURES[@]} -eq 0 ]] && return 0
  echo >&2
  echo -e "  ${RED}${BOLD}✗ ${#PERM_FAILURES[@]} permission(s) could not be assigned:${RESET}" >&2
  local f
  for f in "${PERM_FAILURES[@]}"; do echo -e "      ${RED}•${RESET} ${f}" >&2; done
  echo >&2
  echo    "  Ask someone with the required rights to apply the full set below, then re-run" >&2
  echo    "  this script — or re-run with --skip-permission-assignment once they are in place:" >&2
  echo >&2
  print_required_permissions >&2
  echo >&2
  echo -e "  See the README section ${BOLD}\"Deployment prerequisites (permissions)\"${RESET} for details." >&2
  exit 1
}

# With --skip-permission-assignment, the grant steps are skipped on the assumption
# they were applied out of band. Print the exact set that must already be in place,
# so an admin can verify/apply them. The deploy still starts the app, which
# provisions the view, synced table and sync job.
print_skip_permissions_notice() {
  # NB: `return 0` — a bare `return` here would inherit the failed [[ ]] status (1)
  # and, under `set -e`, silently abort the whole deploy in the default (non-skip) path.
  [[ -n "$SKIP_PERMS" ]] || return 0
  print_step "Skipping permission assignment (--skip-permission-assignment)"
  echo -e "  ${CYAN}⚠${RESET} Assuming these grants are already in place (applied outside this deploy)."
  echo    "    The deploy proceeds normally — starting the app, which provisions the view,"
  echo    "    synced table and sync job. If any are missing, that provisioning fails."
  echo
  print_required_permissions
  echo
  echo -e "  See the README section ${BOLD}\"Deployment prerequisites (permissions)\"${RESET} for details."
}

# No Postgres superuser for the SP: the app's own tables live in a schema the SP
# creates and owns (backend/db/connection.py APP_SCHEMA), using the CREATE-on-database
# right that the app's Lakebase resource (CAN_CONNECT_AND_CREATE) already grants.
grant_lakebase_project_access() {
  [[ -n "$SKIP_PERMS" ]] && return
  print_step "Granting the app service principal access to the Lakebase project"

  # Workspace-level "Can Use" on the Lakebase project — required for the SP to
  # create the synced table into the project.
  local project_name="${LAKEBASE_BRANCH#projects/}"; project_name="${project_name%%/*}"
  if databricks api patch "/api/2.0/permissions/database-projects/${project_name}" \
      "${CLI[@]}" \
      --json "{\"access_control_list\": [{\"service_principal_name\": \"$SP_ID\", \"permission_level\": \"CAN_USE\"}]}" >/dev/null; then
    print_ok "Granted CAN_USE on Lakebase project '$project_name' to the SP"
  else
    _perm_record "'Can Use' on Lakebase project '${project_name}' for the SP"
  fi
}

# At startup the app (as its SP) creates the view, the synced table — whose creation
# runs the initial snapshot — and, last, the classification_sync refresh job, tagged
# with its app_version. Wait for that job — matching the name, the SP as creator AND
# this deploy's version — as the signal that this deploy's provisioning finished. The
# app waits up to 15 min for the synced table's pipeline id, so allow 20 min here.
wait_for_classification_provisioning() {
  print_step "Waiting for the app to provision the view, synced table and sync job (as the SP)"
  local job_id="" i=0
  while [[ -z "$job_id" && $i -lt 80 ]]; do
    job_id=$(databricks jobs list --name "$SYNC_JOB_NAME" "${CLI[@]}" --output json 2>/dev/null \
      | python3 -c "
import sys, json
try:
    jobs = json.load(sys.stdin)
except Exception:
    jobs = []
if isinstance(jobs, dict):
    jobs = jobs.get('jobs') or []
sp, version = sys.argv[1], sys.argv[2]
print(next((str(j['job_id']) for j in jobs
            if j.get('creator_user_name') == sp
            and ((j.get('settings') or {}).get('tags') or {}).get('app_version') == version), ''))
" "$SP_ID" "$APP_VERSION" || true)
    [[ -n "$job_id" ]] || { sleep 15; i=$((i+1)); }
  done
  [[ -n "$job_id" ]] \
    || die "The app did not finish provisioning within 20 minutes — check the app logs for 'classification' errors. Missing grants? See the README section \"Deployment prerequisites (permissions)\"; re-run this script once fixed."

  local state
  state=$(databricks api get "/api/2.0/postgres/synced_tables/${SYNCED_UC_NAME}" "${CLI[@]}" 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['status']['detailed_state'])" 2>/dev/null || echo "unknown")
  print_ok "View ${VIEW_UC} (owned by the SP)"
  print_ok "Synced table ${SYNCED_UC_NAME}: ${state}"
  print_ok "Sync job ${job_id}: pipeline refresh every ${SYNC_INTERVAL_HOURS}h, runs as the SP"
}

bundle_run() {
  print_step "Starting the app"
  echo "  Running: databricks bundle run data-classification-review-app -t prod"
  echo "  (App will connect to Lakebase and run DB migrations on first start)"
  databricks bundle run data-classification-review-app -t prod "${CLI[@]}" \
    || die "bundle run failed — check output above"
  print_ok "App started"
}

# Runs a single GRANT on the warehouse. Returns non-zero on failure so the caller can
# record it (collect-and-summarize) rather than dying with a generic message.
_grant() {
  local stmt="$1" json resp
  json=$(printf '{"statement": "%s", "warehouse_id": "%s", "wait_timeout": "30s"}' \
    "$stmt" "$WAREHOUSE_ID")
  resp=$(databricks api post /api/2.0/sql/statements "${CLI[@]}" --json "$json") || return 1
  echo "$resp" | grep -q 'SUCCEEDED' || return 1
}

grant_sp_provisioning() {
  [[ -n "$SKIP_PERMS" ]] && return
  print_step "Granting the app service principal provisioning access"

  # 1) Target schema: the SP creates and owns the view + synced table here.
  #    ALL PRIVILEGES covers CREATE (view + table) and SELECT on what it owns.
  if _grant "GRANT USE CATALOG ON CATALOG \`${CLASSIFICATION_CATALOG}\` TO \`${SP_ID}\`" \
     && _grant "GRANT ALL PRIVILEGES ON SCHEMA \`${CLASSIFICATION_CATALOG}\`.\`${CLASSIFICATION_SCHEMA}\` TO \`${SP_ID}\`"; then
    print_ok "Granted USE CATALOG + ALL ON SCHEMA on ${CLASSIFICATION_CATALOG}.${CLASSIFICATION_SCHEMA}"
  else
    _perm_record "USE CATALOG + ALL PRIVILEGES on ${CLASSIFICATION_CATALOG}.${CLASSIFICATION_SCHEMA} for the SP"
  fi

  # 2) Source table the view reads. The view executes with the SP owner's
  #    privileges, so the SP (not the installer) needs SELECT here.
  if [[ "$DEMO_MODE" == "mock-results" ]]; then
    local cat sch
    cat="${DEMO_RESULTS_TABLE%%.*}"
    sch="$(echo "$DEMO_RESULTS_TABLE" | cut -d. -f2)"
    if _grant "GRANT USE CATALOG ON CATALOG \`${cat}\` TO \`${SP_ID}\`" \
       && _grant "GRANT USE SCHEMA ON SCHEMA \`${cat}\`.\`${sch}\` TO \`${SP_ID}\`" \
       && _grant "GRANT SELECT ON TABLE ${DEMO_RESULTS_TABLE} TO \`${SP_ID}\`"; then
      print_ok "Granted SELECT on $DEMO_RESULTS_TABLE"
    else
      _perm_record "SELECT on ${DEMO_RESULTS_TABLE} for the SP"
    fi
  else
    if _grant "GRANT USE CATALOG ON CATALOG system TO \`${SP_ID}\`" \
       && _grant "GRANT SELECT ON TABLE system.data_classification.results TO \`${SP_ID}\`"; then
      print_ok "Granted SELECT on system.data_classification.results"
    else
      _perm_record "SELECT on system.data_classification.results for the SP (needs account/metastore admin)"
    fi
  fi
}

run_demo() {
  [[ "$DEMO_MODE" == "none" ]] && return
  print_step "Installing demo: $DEMO_MODE"

  local job_mode="${DEMO_MODE//-/_}"
  local enable_dc="false"
  [[ -n "$DEMO_ENABLE_CLASSIFICATION" ]] && enable_dc="true"

  echo "  Running demo job (demo_mode=$job_mode)..."
  databricks bundle run data-classification-review-demo -t prod "${CLI[@]}" \
    --params "demo_mode=${job_mode},target_catalog=${DEMO_CATALOG},enable_dc=${enable_dc},results_table=${DEMO_RESULTS_TABLE}" \
    || die "Demo job failed — check the run output above"
  print_ok "Demo job completed"
}

print_summary() {
  local app_url="${WORKSPACE_HOST}/apps/data-classification-review-app"
  echo
  echo -e "${BOLD}╔══════════════════════════════════════════╗${RESET}"
  echo -e "${BOLD}║         Deployment complete! ✓           ║${RESET}"
  echo -e "${BOLD}╚══════════════════════════════════════════╝${RESET}"
  echo
  echo -e "  ${BOLD}App URL:${RESET}        $app_url"
  echo -e "  ${BOLD}Workspace:${RESET}      $WORKSPACE_HOST"
  echo -e "  ${BOLD}Warehouse:${RESET}      $WAREHOUSE_NAME"
  echo -e "  ${BOLD}Catalog filter:${RESET} $CATALOG_FILTER"
  echo -e "  ${BOLD}Lakebase:${RESET}       $LAKEBASE_HOST"
  if [[ "$DEMO_MODE" != "none" ]]; then
    echo -e "  ${BOLD}Demo:${RESET}           $DEMO_MODE"
    if [[ "$DEMO_MODE" == "single-catalog" ]]; then
      echo -e "  ${BOLD}Demo catalog:${RESET}   $DEMO_CATALOG"
    fi
    if [[ "$DEMO_MODE" == "single-catalog" || "$DEMO_MODE" == "multi-catalog" ]]; then
      local classification_state="not enabled"
      [[ -n "$DEMO_ENABLE_CLASSIFICATION" ]] && classification_state="enabled"
      echo -e "  ${BOLD}Classification:${RESET} $classification_state"
    fi
    [[ "$DEMO_MODE" == "mock-results" ]] \
      && echo -e "  ${BOLD}Results table:${RESET}  $DEMO_RESULTS_TABLE (app now reads from here)"
  fi
  if [[ -n "$LEGACY_UPGRADE_JOB" ]]; then
    echo
    echo -e "  ${BOLD}Legacy upgrade:${RESET} job \"${LEGACY_UPGRADE_JOB_NAME}\""
    echo    "                  Open the app once, then run the job from the Jobs UI or:"
    echo    "                  databricks bundle run ${LEGACY_UPGRADE_JOB_KEY} -t prod${PROFILE:+ --profile ${PROFILE}}"
  fi
  echo
  echo -e "  ${CYAN}Note:${RESET} databricks.local.yml is gitignored."
  echo    "  Other deployers must run this script on their own machine."
  echo
}

# ── main ─────────────────────────────────────────────────────────────────────
main() {
  parse_args "$@"

  echo
  echo -e "${BOLD}╔══════════════════════════════════════════╗${RESET}"
  echo -e "${BOLD}║  Data Classification Review — Deployer   ║${RESET}"
  echo -e "${BOLD}╚══════════════════════════════════════════╝${RESET}"

  check_prereqs
  auth_login

  [[ -f databricks.local.yml ]] || echo "# placeholder" > databricks.local.yml

  collect_config
  collect_demo_config
  setup_lakebase
  provision_classification_targets   # catalog/schema + derive names/cron
  resolve_deployer                   # → CAN_MANAGE on the sync job the app creates

  # Single deploy: creates/updates the app (and its service principal). The view,
  # synced table and sync job are not bundle resources — the app creates them at
  # startup, as its SP.
  write_local_files
  _bundle_deploy
  discover_sp_id
  print_skip_permissions_notice      # no-op unless --skip-permission-assignment

  # The demo (if any) creates its source table before the app builds the view, then
  # grant the SP everything it needs to create+own the view/synced table and read the
  # source. All grants land before the app starts.
  run_demo
  grant_sp_provisioning
  grant_lakebase_project_access
  report_permission_failures         # summarize + exit if any grant failed (after attempting all)

  bundle_run                         # start the app → view, synced table, sync job (as the SP)
  wait_for_classification_provisioning
  print_summary
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
