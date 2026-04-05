"""Migration runner — versioned, forward-only SQL migrations."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent
OUTPUT_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "output" / "storage"

MIGRATION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(64) PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT NOW(),
    filename TEXT NOT NULL
);
"""

MIGRATION_FILES = [
    ("001_intake", MIGRATIONS_DIR / "schema.sql"),
    ("002_output", OUTPUT_MIGRATIONS_DIR / "schema.sql"),
]


async def run_migrations(pool: Any) -> list[str]:
    """Run all pending migrations. Returns list of applied versions."""
    applied: list[str] = []

    async with pool.acquire() as conn:
        # Create migration tracking table
        await conn.execute(MIGRATION_TABLE)

        # Get already applied migrations
        rows = await conn.fetch("SELECT version FROM schema_migrations ORDER BY version")
        done = {r["version"] for r in rows}

        for version, filepath in MIGRATION_FILES:
            if version in done:
                continue
            if not filepath.exists():
                logger.warning("migration.missing", version=version, path=str(filepath))
                continue

            sql = filepath.read_text()
            try:
                # Run in transaction
                async with conn.transaction():
                    # Split by semicolons and execute each statement
                    for statement in sql.split(";"):
                        stmt = statement.strip()
                        if stmt and not stmt.startswith("--"):
                            try:
                                await conn.execute(stmt)
                            except Exception as e:
                                # Skip "already exists" errors
                                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                                    continue
                                raise

                    await conn.execute(
                        "INSERT INTO schema_migrations (version, filename) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                        version, filepath.name,
                    )
                applied.append(version)
                logger.info("migration.applied", version=version)
            except Exception as e:
                logger.error("migration.failed", version=version, error=str(e))
                raise

    return applied
