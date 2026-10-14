#!/usr/bin/env bash
# Roll production back to the version that was running before the last deploy.
# Run ON the EC2 box.
#
#   scripts/rollback.sh                 # back to the commit recorded by deploy.sh
#   scripts/rollback.sh --to v1.2.0     # any tag/sha (rebuilds from source)
#   scripts/rollback.sh --downgrade-db  # ALSO run 'alembic downgrade' first
#   DRY_RUN=1 scripts/rollback.sh       # show the plan only
#
# Default is code-only: the previous images are restored, the database is left
# alone. That is safe for additive migrations (new tables/columns), which is how
# this project writes them. --downgrade-db reverses the schema and can DROP DATA
# (for example v1.3.0 -> 1.2.x drops the MOM revision table), so it is opt-in;
# the pre-deploy dump named in the state file is the real data safety net.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib_deploy.sh"

TO=""; DOWNGRADE=0; AUTO=0
while [ $# -gt 0 ]; do
  case "$1" in
    --to) TO="${2:-}"; shift ;;
    --downgrade-db) DOWNGRADE=1 ;;
    --auto) AUTO=1 ;;
    *) die "unknown option $1" ;;
  esac
  shift
done

cd "$APP_DIR" || die "cannot cd to $APP_DIR"
prepare_state_dir
STATE="$STATE_DIR/last_good.env"
[ -f "$STATE" ] || [ -n "$TO" ] || die "no rollback point recorded ($STATE); use --to <tag|sha>"
[ -f "$STATE" ] && source "$STATE"

if [ -n "$TO" ]; then
  git fetch --tags --prune origin >/dev/null 2>&1 || true
  TARGET="$(git rev-parse --verify --quiet "$TO^{commit}")" || die "cannot resolve $TO"
  USE_PREV_IMAGES=0
else
  TARGET="${PREV_SHA:-}"; [ -n "$TARGET" ] || die "state file has no PREV_SHA"
  USE_PREV_IMAGES=1
fi
CURRENT="$(git rev-parse HEAD)"
say "Rollback $(short "$CURRENT") -> $(short "$TARGET")"
[ "$AUTO" = "1" ] || { [ "$DRY_RUN" = "1" ] || { read -r -p "Proceed? [y/N] " a; [ "$a" = "y" ] || die "cancelled"; }; }

if [ "$DOWNGRADE" = "1" ]; then
  [ -n "${PREV_ALEMBIC_REV:-}" ] || die "no previous alembic revision recorded; cannot downgrade"
  warn "downgrading database schema to $PREV_ALEMBIC_REV (may drop data)"
  run compose exec -T backend alembic downgrade "$PREV_ALEMBIC_REV" || die "alembic downgrade failed; database untouched beyond that point, backup: ${BACKUP_FILE:-?}"
fi

if [ "$USE_PREV_IMAGES" = "1" ] && docker image inspect app-backend:previous >/dev/null 2>&1 && docker image inspect app-frontend:previous >/dev/null 2>&1; then
  info "restoring the saved images (no rebuild)"
  run docker tag app-backend:previous app-backend:latest
  run docker tag app-frontend:previous app-frontend:latest
  run git checkout -q --detach "$TARGET"
  run compose up -d --no-build --no-deps backend frontend
else
  info "rebuilding from $(short "$TARGET")"
  run git checkout -q --detach "$TARGET"
  run compose build backend frontend || die "rebuild failed"
  run compose up -d --no-deps backend frontend
fi

if [ "$DRY_RUN" = "1" ]; then WANT="(dry-run)"; else WANT="$(backend_version_in_tree)"; fi
# After a code-only rollback the database may be ahead of the old code, so the
# 'alembic at head' check is relaxed here: wait for the right version + frontend.
if [ "$DRY_RUN" != "1" ]; then
  waited=0
  until [ "$(running_version || true)" = "$WANT" ] && [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$FRONTEND_URL" || true)" = "200" ]; do
    [ "$waited" -ge "$HEALTH_TIMEOUT" ] && { log_event "ROLLBACK FAILED to $(short "$TARGET")"; die "rollback target did not become healthy (wanted $WANT). Backup: ${BACKUP_FILE:-?}"; }
    sleep 5; waited=$((waited + 5))
  done
  info "healthy: backend $WANT, frontend 200"
fi
log_event "ROLLBACK OK $(short "$CURRENT") -> $(short "$TARGET") version=$WANT downgrade_db=$DOWNGRADE"
say "Rolled back to $(short "$TARGET") ($WANT)"
[ "$DOWNGRADE" = "1" ] || info "database was NOT changed. Pre-deploy dump if you need it: ${BACKUP_FILE:-see $BACKUP_DIR}"
exit 0
