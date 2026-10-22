#!/usr/bin/env bash
# Local CI gate -- the same checks as .github/workflows/ci.yml, run in Docker so
# the result does not depend on GitHub Actions being available (billing lock,
# outage) or on what is installed on this machine.
#
# Usage (repo root, needs Docker):
#   scripts/ci_local.sh              # all checks
#   scripts/ci_local.sh backend      # only: backend | frontend | version
#
# Exit code 0 = gate passed. Anything else = do not merge / deploy.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
WHAT="${1:-all}"
NET="fluidgo-ci-$$"
PG="fluidgo-ci-pg-$$"
declare -a RESULTS=()
FAILED=0

record() {  # name rc
  if [ "$2" -eq 0 ]; then RESULTS+=("PASS  $1"); else RESULTS+=("FAIL  $1"); FAILED=1; fi
}

cleanup() {
  docker rm -f "$PG" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

run_version() {
  echo "== Version strings agree =="
  # CI_RELEASE_REF (set by deploy.sh's gate step to the tag being deployed,
  # e.g. "v1.4.2") makes this ALSO check the files against the actual
  # release tag, not just against each other. Without it, three files that
  # all forgot to bump still "agree" and the gate passes silently — exactly
  # what happened on v1.4.1 (2026-10-22): version.py/version.ts/package.json
  # stayed at 1.4.0 while the tag moved to 1.4.1, and nothing caught it
  # because deploy.sh never told this script what tag it was deploying.
  # GitHub Actions CI still gets the equivalent for free via GITHUB_REF_NAME
  # (check_version_sync.py already reads that) — this just closes the same
  # gap on the manual EC2 deploy path.
  python3 scripts/check_version_sync.py ${CI_RELEASE_REF:+"$CI_RELEASE_REF"}
  record "Version strings agree" $?
}

run_backend() {
  echo "== Backend: migrations + tests (python 3.11, postgres 15) =="
  docker network create "$NET" >/dev/null || { record "Backend (docker network)" 1; return; }
  docker run -d --name "$PG" --network "$NET" \
    -e POSTGRES_DB=fluidgo_ci -e POSTGRES_USER=fluidgo -e POSTGRES_PASSWORD=ci_test_pass \
    postgres:15-alpine >/dev/null || { record "Backend (start postgres)" 1; return; }
  for _ in $(seq 1 30); do
    docker exec "$PG" pg_isready -U fluidgo >/dev/null 2>&1 && break
    sleep 1
  done
  docker run --rm --network "$NET" -v "$ROOT/backend:/app:ro" -w /app \
    -e DATABASE_URL="postgresql+asyncpg://fluidgo:ci_test_pass@$PG:5432/fluidgo_ci" \
    -e JWT_SECRET=ci-test-secret-not-for-production \
    -e OLLAMA_URL=http://localhost:11434 \
    -e PYTHONDONTWRITEBYTECODE=1 -e PIP_DISABLE_PIP_VERSION_CHECK=1 \
    python:3.11-slim bash -euo pipefail -c '
      pip install -q --no-cache-dir -r requirements.txt
      heads=$(alembic heads | grep -c "(head)")
      echo "alembic heads: $heads"
      test "$heads" -eq 1
      alembic upgrade head
      alembic downgrade -1
      alembic upgrade head
      python -m pytest -q -p no:cacheprovider
    '
  record "Backend (single head, migrations, reversible, tests)" $?
}

run_frontend() {
  echo "== Frontend: typecheck + build (node 20) =="
  # Work on a copy so the build never writes node_modules/dist into the repo.
  docker run --rm -v "$ROOT/frontend:/src:ro" -w /work node:20-alpine sh -euc '
    cp -r /src/. /work/
    npm install --legacy-peer-deps --no-audit --no-fund --silent
    npm run build
  '
  record "Frontend (tsc + vite build)" $?
}

case "$WHAT" in
  all)      run_version; run_backend; run_frontend ;;
  version)  run_version ;;
  backend)  run_backend ;;
  frontend) run_frontend ;;
  *) echo "usage: $0 [all|version|backend|frontend]"; exit 2 ;;
esac

echo
echo "================ CI GATE ================"
printf '%s\n' "${RESULTS[@]}"
if [ "$FAILED" -eq 0 ]; then echo "GATE: PASSED"; else echo "GATE: FAILED"; fi
exit "$FAILED"
