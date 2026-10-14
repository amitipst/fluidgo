# Deploying fluidGo (EC2, no GitHub Actions needed)

All commands run **on the EC2 box** (VS Code SSH terminal), in `/opt/fluidgo/app`.

## Release
1. Merge the change to `main` through a PR, update `CHANGELOG.md` + version (`python3 scripts/check_version_sync.py`).
2. Tag it on GitHub (Releases -> new release, e.g. `v1.3.1`, target `main`).
3. On EC2:
   ```
   cd /opt/fluidgo/app
   scripts/deploy.sh v1.3.1
   ```
   It runs the CI gate on that exact commit, takes a verified `pg_dump`, builds the new images while the
   site keeps serving, swaps backend+frontend, then checks `/api/health` (right version), the frontend (200)
   and `alembic current` (head). If any check fails it rolls back automatically.
4. Smoke-test https://fluidgo.wepsol.com (hard refresh), then done.

`DRY_RUN=1 scripts/deploy.sh v1.3.1` prints the plan and changes nothing.

## Roll back
```
scripts/rollback.sh                 # to the commit/images that were live before the last deploy (no rebuild)
scripts/rollback.sh --to v1.2.0     # to any tag or commit (rebuilds)
scripts/rollback.sh --downgrade-db  # also reverse the schema (can DROP DATA, e.g. MOM tables for 1.3.0 -> 1.2.x)
```
Default rollback is code-only and leaves the database alone, which is safe for additive migrations.
The pre-deploy dump (`/home/ubuntu/backups/fluidgo_prod_pre-deploy_<sha>_<time>.dump`) is the data safety net:
`docker compose -f docker-compose.prod.yml exec -T db pg_restore -U fluidgo -d fluidgo --clean --if-exists < DUMP`.

## The gate on its own
`scripts/ci_local.sh [all|backend|frontend|version]` (needs Docker). Same checks as `.github/workflows/ci.yml`
(which is manual-only because Actions runs on the free account can be blocked by billing).

## Files
- `scripts/deploy.sh`, `scripts/rollback.sh`, `scripts/lib_deploy.sh`, `scripts/ci_local.sh`
- State: `/opt/fluidgo/deploy_state/last_good.env` (previous commit, version, alembic revision, backup file)
- History: `/opt/fluidgo/deployments.log`
- Note: after a deploy the checkout is a detached HEAD at the deployed commit (so `git pull` will refuse; use `deploy.sh`).
