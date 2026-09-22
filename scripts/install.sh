#!/usr/bin/env bash
# scripts/install.sh — build from source, then deploy via scripts/deploy.sh
#
# This script ONLY builds the artifacts (React frontend + Python wheel into
# .build/) and then hands off to scripts/deploy.sh for the actual deployment.
# All deployment logic — auth, config, Lakebase, grants, flags — lives in
# deploy.sh; this avoids duplicating (and drifting from) that pipeline.
#
# Any arguments are forwarded verbatim to deploy.sh, so install.sh supports the
# same interactive and non-interactive (--yes, --profile, ...) modes. Run
# `./scripts/deploy.sh --help` for the full flag list.
#
# NOTE: this script does not bump pyproject.toml's version. Databricks Apps
# skips reinstalling a wheel whose version matches what's already installed,
# so bump the version by hand before running this script whenever you need
# a deploy to actually pick up new code.
set -euo pipefail

# ── formatting ──────────────────────────────────────────────────────────────
BOLD='\033[1m'; RESET='\033[0m'; GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'

print_step() { echo; echo -e "${CYAN}${BOLD}▶ $1${RESET}"; }
print_ok()   { echo -e "  ${GREEN}✓${RESET} $1"; }
die()        { echo -e "  ${RED}✗ $1${RESET}" >&2; exit 1; }

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# ── build prerequisites ───────────────────────────────────────────────────────
check_build_prereqs() {
  print_step "Checking build prerequisites"
  command -v npm >/dev/null 2>&1 || die "npm not found — required to build the frontend"
  command -v apx >/dev/null 2>&1 || die "apx not found — install from https://github.com/databricks-solutions/apx"
  print_ok "Build tools found (npm, apx)"
}

# ── build ─────────────────────────────────────────────────────────────────────
build() {
  print_step "Building from source"

  # Run the build explicitly here so it uses the current shell's PATH (which has
  # nvm-managed npm and ~/.local/bin/apx). DABs spawns a subprocess for
  # artifacts.build that may not inherit custom PATH entries.
  echo "  Installing frontend dependencies..."
  (cd frontend && npm install) || die "npm install failed — is npm in PATH?"
  echo "  Building frontend..."
  (cd frontend && npm run build) || die "Frontend build failed"

  echo "  Packaging Python wheel..."
  apx build --skip-ui-build || die "apx build failed — is apx in PATH?"
  print_ok "Build complete — artifacts written to .build/"
}

# ── main ─────────────────────────────────────────────────────────────────────
main() {
  echo
  echo -e "${BOLD}╔══════════════════════════════════════════╗${RESET}"
  echo -e "${BOLD}║  Data Classification Review — Installer  ║${RESET}"
  echo -e "${BOLD}╚══════════════════════════════════════════╝${RESET}"

  check_build_prereqs
  build

  print_step "Handing off to deploy.sh"
  echo "  Build done — running scripts/deploy.sh for deployment"
  # Replace this process with deploy.sh, forwarding all original arguments.
  exec "${SCRIPT_DIR}/deploy.sh" "$@"
}

main "$@"
