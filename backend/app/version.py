"""Single backend source of truth for the app version (semantic versioning).

Imported by app.main for the OpenAPI title block and /api/health, so the
running server can report which release it is. Bump together with
frontend/src/version.ts and frontend/package.json at each release;
scripts/check_version_sync.py fails if they drift apart or if a release tag
does not match.
"""
APP_VERSION = "1.6.0"
