"""Ensures app.config.Settings() can be instantiated at import time without a real
.env / running Postgres — required env vars get harmless test values. Tests in this
suite are pure-function or mocked-repository tests and never open a real DB connection."""
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
