#!/usr/bin/env bash
# Shared helpers for deploy.sh / rollback.sh. Source it, do not execute it.

APP_DIR="${APP_DIR:-/opt/fluidgo/app}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-/home/ubuntu/backups}"
STATE_DIR="${STATE_DIR:-/opt/fluidgo/deploy_state}"
LOG_FILE="${LOG_FILE:-/opt/fluidgo/deployments.log}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/api/health}"
FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:3000/}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-120}"
DRY_RUN="${DRY_RUN:-0}"

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
info() { printf '   %s\n' "$*"; }
warn() { printf '\033[33m!! %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31mXX %s\033[0m\n' "$*" >&2; exit 1; }

# Mutating commands go through run() so DRY_RUN=1 only prints them.
run() {
  if [ "$DRY_RUN" = "1" ]; then printf '   [dry-run] %s\n' "$*"; return 0; fi
  "$@"
}

compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

log_event() {  # appended to the existing deployments log, never fatal
  [ "$DRY_RUN" = "1" ] && return 0
  { echo "$(date -u +%FT%TZ) $*" >> "$LOG_FILE"; } 2>/dev/null || true
}

prepare_state_dir() {
  mkdir -p "$STATE_DIR" 2>/dev/null || { STATE_DIR="$HOME/.fluidgo_deploy"; mkdir -p "$STATE_DIR"; }
}

short() { git rev-parse --short "$1"; }

backend_version_in_tree() {  # version declared by the code in the CURRENT checkout
  sed -n 's/^APP_VERSION *= *"\([^"]*\)".*/\1/p' backend/app/version.py
}

running_version() {
  curl -fsS --max-time 5 "$HEALTH_URL" 2>/dev/null | sed -n 's/.*"version" *: *"\([^"]*\)".*/\1/p'
}

running_alembic_rev() {
  compose exec -T backend alembic current 2>/dev/null | grep -Eo '^[0-9a-zA-Z_]+' | tail -1
}

# wait_healthy <expected_version>  -> 0 when backend reports that version, the
# frontend answers 200 and alembic is at head; 1 on timeout.
wait_healthy() {
  local want="$1" waited=0 got fe
  [ "$DRY_RUN" = "1" ] && { info "[dry-run] would wait for version $want"; return 0; }
  while [ "$waited" -lt "$HEALTH_TIMEOUT" ]; do
    got="$(running_version || true)"
    if [ "$got" = "$want" ]; then
      fe="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$FRONTEND_URL" || true)"
      if [ "$fe" = "200" ]; then
        if compose exec -T backend alembic current 2>/dev/null | grep -q '(head)'; then
          info "healthy: backend $got, frontend 200, alembic at head (${waited}s)"
          return 0
        fi
      fi
    fi
    sleep 5; waited=$((waited + 5))
  done
  warn "not healthy after ${HEALTH_TIMEOUT}s (backend reports '${got:-nothing}', wanted '$want', frontend '${fe:-?}')"
  return 1
}

write_state() {  # write_state KEY=VALUE ...   (overwrites last_good.env)
  [ "$DRY_RUN" = "1" ] && { info "[dry-run] would record rollback point"; return 0; }
  prepare_state_dir
  : > "$STATE_DIR/last_good.env"
  for kv in "$@"; do echo "$kv" >> "$STATE_DIR/last_good.env"; done
}
