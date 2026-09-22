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

# ── globals ──────────────────────────────────────────────────────────────────
PROFILE=""
CLI=()
WORKSPACE_HOST=""
WAREHOUSE_NAME=""
WAREHOUSE_ID=""
CATALOG_FILTER=""
ADMIN_EMAILS=""
LAKEBASE_BRANCH=""
LAKEBASE_DATABASE=""
LAKEBASE_HOST=""
LAKEBASE_ENDPOINT_NAME=""
SP_ID=""
NEW_LAKEBASE=""
YES_MODE=""
DEMO_MODE=""
DEMO_CATALOG=""
DEMO_ENABLE_CLASSIFICATION=""
DEMO_RESULTS_TABLE=""

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
  --lakebase-branch PATH      Existing branch   (e.g. projects/<id>/branches/<id>)
  --lakebase-database PATH    Existing database (e.g. projects/<id>/branches/<id>/databases/databricks-postgres)
  --lakebase-host HOST        Existing endpoint host
  --lakebase-endpoint-name N  Existing endpoint name
  --new-lakebase              Provision a brand-new Lakebase instance

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
  -y, --yes                   Non-interactive mode; fail if required params are missing
  -h, --help                  Show this help

Examples:
  # Fully non-interactive (env-var auth, existing Lakebase)
  export DATABRICKS_HOST=https://my.azuredatabricks.net
  export DATABRICKS_TOKEN=dapi...
  $(basename "$0") --admin-emails me@co.com --warehouse-name "Shared" \\
    --lakebase-branch "projects/x/branches/production" \\
    --lakebase-database "projects/x/branches/production/databases/databricks-postgres" \\
    --lakebase-host "ep-xxx.database.azuredatabricks.net" \\
    --lakebase-endpoint-name "projects/x/branches/production/endpoints/primary" \\
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
      --lakebase-branch)        LAKEBASE_BRANCH="$2";        shift 2 ;;
      --lakebase-database)      LAKEBASE_DATABASE="$2";      shift 2 ;;
      --lakebase-host)          LAKEBASE_HOST="$2";          shift 2 ;;
      --lakebase-endpoint-name) LAKEBASE_ENDPOINT_NAME="$2"; shift 2 ;;
      --new-lakebase)           NEW_LAKEBASE=1;              shift ;;
      --demo)                   DEMO_MODE="$2";              shift 2 ;;
      --demo-catalog)           DEMO_CATALOG="$2";           shift 2 ;;
      --demo-enable-classification) DEMO_ENABLE_CLASSIFICATION=1; shift ;;
      --demo-results-table)     DEMO_RESULTS_TABLE="$2";     shift 2 ;;
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
  local ep_json
  ep_json=$(databricks postgres create-endpoint \
    "projects/$project_id/branches/$branch_id" "$endpoint_id" \
    "${CLI[@]}" --output json 2>/dev/null || true)

  local host=""
  host=$(echo "$ep_json" | grep '"host"' | head -1 | cut -d'"' -f4 || true)
  if [[ -z "$host" ]]; then
    local ep_path="projects/$project_id/branches/$branch_id/endpoints/$endpoint_id"
    local i=0
    while [[ -z "$host" && $i -lt 12 ]]; do
      host=$(databricks postgres get-endpoint "$ep_path" \
        --output json "${CLI[@]}" 2>/dev/null \
        | grep '"host"' | head -1 | cut -d'"' -f4 || true)
      [[ -n "$host" ]] || { sleep 5; i=$((i+1)); }
    done
  fi
  [[ -n "$host" ]] || die "Timed out waiting for endpoint host"

  LAKEBASE_BRANCH="projects/$project_id/branches/$branch_id"
  LAKEBASE_DATABASE="projects/$project_id/branches/$branch_id/databases/databricks-postgres"
  LAKEBASE_HOST="$host"
  LAKEBASE_ENDPOINT_NAME="projects/$project_id/branches/$branch_id/endpoints/$endpoint_id"
  print_ok "Endpoint host: $LAKEBASE_HOST"
}

setup_lakebase() {
  print_step "Lakebase setup"

  # Non-interactive: all 4 params provided → use existing instance
  if [[ -n "$LAKEBASE_BRANCH" && -n "$LAKEBASE_DATABASE" && -n "$LAKEBASE_HOST" && -n "$LAKEBASE_ENDPOINT_NAME" ]]; then
    print_ok "Using existing instance: $LAKEBASE_HOST"
    return
  fi

  # Non-interactive: --new-lakebase flag → provision new
  if [[ -n "$NEW_LAKEBASE" ]]; then
    _lakebase_new
    return
  fi

  # --yes mode but no lakebase config provided
  if [[ -n "$YES_MODE" ]]; then
    die "Non-interactive mode requires either all --lakebase-* params (existing instance) or --new-lakebase"
  fi

  # Interactive
  if confirm "Do you have an existing Lakebase Autoscaling instance?"; then
    read -r -p "  Branch path (e.g. projects/<id>/branches/<id>): " LAKEBASE_BRANCH
    read -r -p "  Database path (e.g. projects/<id>/branches/<id>/databases/databricks-postgres): " LAKEBASE_DATABASE
    read -r -p "  Endpoint host (e.g. ep-xxx.database.westeurope.azuredatabricks.net): " LAKEBASE_HOST
    read -r -p "  Endpoint name (e.g. projects/<id>/branches/<id>/endpoints/primary): " LAKEBASE_ENDPOINT_NAME
    [[ -n "$LAKEBASE_BRANCH" && -n "$LAKEBASE_DATABASE" && -n "$LAKEBASE_HOST" && -n "$LAKEBASE_ENDPOINT_NAME" ]] \
      || die "All Lakebase fields are required"
    print_ok "Using existing instance: $LAKEBASE_HOST"
  else
    _lakebase_new
  fi
}

# ── local files ───────────────────────────────────────────────────────────────
write_local_files() {
  print_step "Writing local configuration"

  local catalog_filter_block=""
  if [[ -n "$CATALOG_FILTER" ]]; then
    catalog_filter_block="    resources:
      apps:
        data-classification-review-app:
          config:
            env:
              - name: CLASSIFICATION_CATALOG_FILTER
                value: \"${CATALOG_FILTER}\""
  fi

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
      admin_emails: "${ADMIN_EMAILS}"
${results_table_block}
${catalog_filter_block}
YAML
  print_ok "databricks.local.yml written"

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

# ── deploy ───────────────────────────────────────────────────────────────────
bundle_deploy() {
  print_step "Deploying bundle"

  rm -rf .databricks/bundle/prod/
  print_ok "Local bundle cache cleared"

  echo "  Running: databricks bundle deploy -t prod ${CLI[*]}"
  echo "  (Uploading pre-built artifacts — may take a few minutes)"
  databricks bundle deploy -t prod --force-lock "${CLI[@]}" \
    || die "bundle deploy failed — check output above"
  print_ok "Bundle deployed"
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

create_lakebase_role() {
  print_step "Configuring Lakebase role for service principal"

  local role_path="${LAKEBASE_BRANCH}/roles/dbrx-apps-${SP_ID}"

  databricks postgres update-role "$role_path" \
    "spec.membership_roles" \
    "${CLI[@]}" \
    --json "{\"spec\": {\"membership_roles\": [\"DATABRICKS_SUPERUSER\"], \"postgres_role\": \"$SP_ID\"}}" \
    || die "Failed to grant DATABRICKS_SUPERUSER to SP role — check that bundle deploy completed successfully"
  print_ok "Granted DATABRICKS_SUPERUSER to SP role (dbrx-apps-${SP_ID})"
}

bundle_run() {
  print_step "Starting the app"
  echo "  Running: databricks bundle run data-classification-review-app -t prod"
  echo "  (App will connect to Lakebase and run DB migrations on first start)"
  databricks bundle run data-classification-review-app -t prod "${CLI[@]}" \
    || die "bundle run failed — check output above"
  print_ok "App started"
}

_grant() {
  local stmt="$1" json resp
  json=$(printf '{"statement": "%s", "warehouse_id": "%s", "wait_timeout": "30s"}' \
    "$stmt" "$WAREHOUSE_ID")
  resp=$(databricks api post /api/2.0/sql/statements "${CLI[@]}" --json "$json") \
    || die "GRANT request failed: $stmt"
  echo "$resp" | grep -q 'SUCCEEDED' || die "GRANT failed: $stmt"$'\n'"$resp"
}

grant_system_table() {
  print_step "Granting service principal access to the classification source table"

  if [[ "$DEMO_MODE" == "mock-results" ]]; then
    local cat sch
    cat="${DEMO_RESULTS_TABLE%%.*}"
    sch="$(echo "$DEMO_RESULTS_TABLE" | cut -d. -f2)"
    _grant "GRANT USE CATALOG ON CATALOG \`${cat}\` TO \`${SP_ID}\`"
    _grant "GRANT USE SCHEMA ON SCHEMA \`${cat}\`.\`${sch}\` TO \`${SP_ID}\`"
    _grant "GRANT SELECT ON TABLE ${DEMO_RESULTS_TABLE} TO \`${SP_ID}\`"
    print_ok "Granted SELECT on $DEMO_RESULTS_TABLE"
    return
  fi

  _grant "GRANT USE CATALOG ON CATALOG system TO \`${SP_ID}\`"
  _grant "GRANT SELECT ON TABLE system.data_classification.results TO \`${SP_ID}\`"
  print_ok "Granted SELECT on system.data_classification.results"
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
  write_local_files
  bundle_deploy
  discover_sp_id
  create_lakebase_role
  bundle_run
  run_demo
  grant_system_table
  print_summary
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
