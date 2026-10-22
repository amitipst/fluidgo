#!/usr/bin/env bash
# Safe production deploy, run ON the EC2 box (for example from the VS Code SSH
# terminal). Does not need GitHub Actions.
#
#   scripts/deploy.sh v1.3.1            # deploy a tag (or branch / full SHA)
#   scripts/deploy.sh v1.3.1 --skip-gate  # emergency only: skip the CI gate
#   DRY_RUN=1 scripts/deploy.sh v1.3.1  # print what would happen, change nothing
#
# What it does, in order. Nothing touches the running site until step 5:
#   1 preflight   clean tree, disk space, docker reachable
#   2 resolve     fetch tags, resolve the ref to a commit
#   3 gate        run scripts/ci_local.sh on that exact commit (temp worktree)
#   4 backup      pg_dump -Fc, verified readable; remember current commit,
#                 alembic revision and keep the running images as ':previous'
#   5 swap        checkout, build backend+frontend, up -d --no-deps
#   6 verify      /api/health reports the new version, frontend 200, alembic head
#   7 on failure  automatic rollback to the previous commit/images
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib_deploy.sh"

REF="${1:-}"; SKIP_GATE=0
[ -n "$REF" ] || die "usage: $0 <tag|branch|sha> [--skip-gate]"
[ "${2:-}" = "--skip-gate" ] && SKIP_GATE=1

cd "$APP_DIR" || die "cannot cd to $APP_DIR"
prepare_state_dir

say "1/7 Preflight"
if [ "$DRY_RUN" != "1" ]; then
  docker info >/dev/null 2>&1 || die "docker is not reachable"
  [ -f "$COMPOSE_FILE" ] || die "$COMPOSE_FILE not found in $APP_DIR"
fi
[ -z "$(git status --porcelain --untracked-files=no)" ] || die "working tree has local changes; commit or stash them first (git status)"
avail_gb=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
[ "${avail_gb:-0}" -ge 5 ] || die "only ${avail_gb}G free on /, need at least 5G (run docker builder prune -f)"
info "disk free: ${avail_gb}G"

say "2/7 Resolve $REF"
git fetch --tags --prune origin >/dev/null 2>&1 || die "git fetch failed (network or auth)"
NEW_SHA="$(git rev-parse --verify --quiet "$REF^{commit}" || git rev-parse --verify --quiet "origin/$REF^{commit}")" || true
[ -n "$NEW_SHA" ] || die "cannot resolve '$REF' to a commit"
PREV_SHA="$(git rev-parse HEAD)"
info "current: $(short "$PREV_SHA")   target: $(short "$NEW_SHA") ($REF)"
[ "$NEW_SHA" != "$PREV_SHA" ] || warn "target equals the commit already deployed; continuing (rebuild)"

say "3/7 CI gate on $(short "$NEW_SHA")"
if [ "$SKIP_GATE" = "1" ]; then
  warn "gate skipped by --skip-gate"
elif [ "$DRY_RUN" = "1" ]; then
  info "[dry-run] would run scripts/ci_local.sh in a temp worktree"
else
  GATE_DIR="$(mktemp -d /var/tmp/fluidgo-gate.XXXXXX)"
  git worktree add --detach "$GATE_DIR" "$NEW_SHA" >/dev/null 2>&1 || die "could not create gate worktree"
  # Tell the gate which tag it's actually deploying, so the version-sync
  # check can catch a forgotten version bump (see ci_local.sh's run_version).
  ( cd "$GATE_DIR" && CI_RELEASE_REF="$REF" scripts/ci_local.sh ); gate_rc=$?
  git worktree remove --force "$GATE_DIR" >/dev/null 2>&1 || true
  [ "$gate_rc" -eq 0 ] || die "CI gate FAILED, nothing was changed on the server"
fi

say "4/7 Backup and rollback point"
PREV_VERSION="$(running_version || true)"
PREV_REV="$(running_alembic_rev || true)"
STAMP="$(date +%Y%m%d_%H%M)"
BACKUP_FILE="$BACKUP_DIR/fluidgo_prod_pre-deploy_$(short "$NEW_SHA")_$STAMP.dump"
run mkdir -p "$BACKUP_DIR"
if [ "$DRY_RUN" != "1" ]; then
  compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > "$BACKUP_FILE" \
    || { rm -f "$BACKUP_FILE"; die "pg_dump failed, aborting before any change"; }
  [ -s "$BACKUP_FILE" ] || die "backup file is empty, aborting"
  compose exec -T db pg_restore --list < "$BACKUP_FILE" >/dev/null 2>&1 || die "backup is not a readable dump, aborting"
  info "backup ok: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
else
  info "[dry-run] would write $BACKUP_FILE"
fi
# keep the running images so a rollback needs no rebuild
run docker tag app-backend:latest app-backend:previous 2>/dev/null || true
run docker tag app-frontend:latest app-frontend:previous 2>/dev/null || true
write_state "PREV_SHA=$PREV_SHA" "PREV_VERSION=$PREV_VERSION" "PREV_ALEMBIC_REV=$PREV_REV" \
            "BACKUP_FILE=$BACKUP_FILE" "NEW_SHA=$NEW_SHA" "DEPLOYED_AT=$(date -u +%FT%TZ)"
info "rollback point: commit $(short "$PREV_SHA"), version ${PREV_VERSION:-?}, alembic ${PREV_REV:-?}"

say "5/7 Build and swap (site stays up during the build)"
run git checkout -q --detach "$NEW_SHA" || die "git checkout failed"
EXPECT="$([ "$DRY_RUN" = "1" ] && git show "$NEW_SHA:backend/app/version.py" | sed -n 's/^APP_VERSION *= *"\([^"]*\)".*/\1/p' || backend_version_in_tree)"
info "expecting version $EXPECT"
if ! run compose build backend frontend; then
  warn "build failed; the old containers are still running untouched"
  run git checkout -q --detach "$PREV_SHA"
  log_event "DEPLOY FAILED(build) target=$(short "$NEW_SHA") ref=$REF"
  exit 1
fi
run compose up -d --no-deps backend frontend

say "6/7 Verify"
if wait_healthy "$EXPECT"; then
  say "7/7 Done"
  log_event "DEPLOY OK $(short "$NEW_SHA") ref=$REF version=$EXPECT prev=$(short "$PREV_SHA") backup=$BACKUP_FILE"
  info "deployed $REF ($(short "$NEW_SHA")), version $EXPECT"
  info "to undo:  scripts/rollback.sh"
  exit 0
fi

say "7/7 FAILED, rolling back automatically"
log_event "DEPLOY FAILED(health) target=$(short "$NEW_SHA") ref=$REF; rolling back to $(short "$PREV_SHA")"
if "$HERE/rollback.sh" --auto; then
  warn "rolled back to $(short "$PREV_SHA") (version ${PREV_VERSION:-?}); the new release did NOT go live"
else
  warn "AUTOMATIC ROLLBACK FAILED. Backup: $BACKUP_FILE. Run scripts/rollback.sh or restore by hand."
fi
exit 1
