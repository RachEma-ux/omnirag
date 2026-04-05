"""Repository — PostgreSQL persistence for intake + output models.

Uses asyncpg for async operations with sync fallback to in-memory.
All methods are idempotent (upsert semantics).
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# SQL schema path
INTAKE_SCHEMA = Path(__file__).parent / "schema.sql"
OUTPUT_SCHEMA = Path(__file__).parent.parent.parent / "output" / "storage" / "schema.sql"


class Repository:
    """Persistent storage for the RAG platform.

    Connects to PostgreSQL via DATABASE_URL env var.
    Falls back to in-memory dicts when DB is unavailable.
    """

    def __init__(self) -> None:
        self._pool: Any = None
        self._in_memory = True
        self._tables: dict[str, dict[str, dict]] = {
            "connectors": {},
            "sync_jobs": {},
            "source_cursors": {},
            "source_objects": {},
            "canonical_documents": {},
            "chunks": {},
            "acl_snapshots": {},
            "dead_letters": {},
            "tombstones": {},
            "lineage_events": {},
            "output_chunks": {},
            "output_documents": {},
            "answer_logs": {},
            "webhook_registrations": {},
        }

    async def connect(self) -> bool:
        """Connect to PostgreSQL. Returns True if successful."""
        dsn = os.environ.get("DATABASE_URL") or os.environ.get(
            "POSTGRES_DSN", "postgres://postgres:postgres@localhost:5432/omnirag"
        )
        try:
            import asyncpg
            self._pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10, command_timeout=30)
            # Run migrations
            async with self._pool.acquire() as conn:
                for schema_file in (INTAKE_SCHEMA, OUTPUT_SCHEMA):
                    if schema_file.exists():
                        sql = schema_file.read_text()
                        await conn.execute(sql)
            self._in_memory = False
            logger.info("repository.connected", dsn=dsn.split("@")[-1])
            return True
        except ImportError:
            logger.warning("repository.no_asyncpg", msg="asyncpg not installed, using in-memory")
            return False
        except Exception as e:
            logger.warning("repository.connect_failed", error=str(e), msg="using in-memory fallback")
            return False

    @property
    def is_persistent(self) -> bool:
        return not self._in_memory

    # ─── Generic CRUD ───

    async def upsert(self, table: str, id_field: str, record: dict) -> bool:
        """Insert or update a record."""
        record_id = record.get(id_field, "")

        if not self._in_memory and self._pool:
            try:
                async with self._pool.acquire() as conn:
                    columns = list(record.keys())
                    values = []
                    for v in record.values():
                        if isinstance(v, (dict, list)):
                            values.append(json.dumps(v))
                        else:
                            values.append(v)

                    placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
                    col_names = ", ".join(f'"{c}"' for c in columns)
                    updates = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in columns if c != id_field)

                    sql = f"""
                        INSERT INTO {table} ({col_names})
                        VALUES ({placeholders})
                        ON CONFLICT ("{id_field}") DO UPDATE SET {updates}
                    """
                    await conn.execute(sql, *values)
                    return True
            except Exception as e:
                logger.error("repository.upsert_error", table=table, error=str(e))

        # In-memory fallback
        self._tables.setdefault(table, {})[record_id] = record
        return True

    async def get(self, table: str, id_field: str, id_value: str) -> dict | None:
        """Get a single record by ID."""
        if not self._in_memory and self._pool:
            try:
                async with self._pool.acquire() as conn:
                    row = await conn.fetchrow(f'SELECT * FROM {table} WHERE "{id_field}" = $1', id_value)
                    if row:
                        return dict(row)
            except Exception as e:
                logger.error("repository.get_error", table=table, error=str(e))

        return self._tables.get(table, {}).get(id_value)

    async def list_all(self, table: str, limit: int = 100, where: dict | None = None) -> list[dict]:
        """List records from a table."""
        if not self._in_memory and self._pool:
            try:
                async with self._pool.acquire() as conn:
                    sql = f"SELECT * FROM {table}"
                    params: list = []
                    if where:
                        conditions = []
                        for i, (k, v) in enumerate(where.items()):
                            conditions.append(f'"{k}" = ${i+1}')
                            params.append(v)
                        sql += " WHERE " + " AND ".join(conditions)
                    sql += f" ORDER BY created_at DESC LIMIT {limit}"
                    rows = await conn.fetch(sql, *params)
                    return [dict(r) for r in rows]
            except Exception as e:
                logger.error("repository.list_error", table=table, error=str(e))

        records = list(self._tables.get(table, {}).values())
        if where:
            for k, v in where.items():
                records = [r for r in records if r.get(k) == v]
        return records[:limit]

    async def delete(self, table: str, id_field: str, id_value: str) -> bool:
        """Delete a record."""
        if not self._in_memory and self._pool:
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(f'DELETE FROM {table} WHERE "{id_field}" = $1', id_value)
                    return True
            except Exception as e:
                logger.error("repository.delete_error", table=table, error=str(e))

        table_data = self._tables.get(table, {})
        if id_value in table_data:
            del table_data[id_value]
            return True
        return False

    async def count(self, table: str) -> int:
        """Count records in a table."""
        if not self._in_memory and self._pool:
            try:
                async with self._pool.acquire() as conn:
                    row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM {table}")
                    return row["cnt"] if row else 0
            except Exception:
                pass

        return len(self._tables.get(table, {}))

    # ─── Specialized queries ───

    async def save_job(self, job_dict: dict) -> bool:
        return await self.upsert("sync_jobs", "id", job_dict)

    async def save_source_object(self, obj_dict: dict) -> bool:
        return await self.upsert("source_objects", "id", obj_dict)

    async def save_document(self, doc_dict: dict) -> bool:
        return await self.upsert("canonical_documents", "id", doc_dict)

    async def save_chunk(self, chunk_dict: dict) -> bool:
        return await self.upsert("chunks", "id", chunk_dict)

    async def save_lineage_event(self, event_dict: dict) -> bool:
        return await self.upsert("lineage_events", "id", event_dict)

    async def save_dead_letter(self, letter_dict: dict) -> bool:
        return await self.upsert("dead_letters", "id", letter_dict)

    async def save_tombstone(self, tombstone_dict: dict) -> bool:
        return await self.upsert("tombstones", "id", tombstone_dict)

    async def save_acl_snapshot(self, snapshot_dict: dict) -> bool:
        return await self.upsert("acl_snapshots", "id", snapshot_dict)

    async def save_answer_log(self, log_dict: dict) -> bool:
        return await self.upsert("answer_logs", "id", log_dict)

    async def update_cursor(self, connector_id: str, cursor_value: str) -> bool:
        return await self.upsert("source_cursors", "connector_id", {
            "connector_id": connector_id,
            "cursor_value": cursor_value,
            "updated_at": time.time(),
        })

    async def get_cursor(self, connector_id: str) -> str | None:
        record = await self.get("source_cursors", "connector_id", connector_id)
        return record.get("cursor_value") if record else None

    def status(self) -> dict:
        """Return repository status."""
        if self._in_memory:
            counts = {k: len(v) for k, v in self._tables.items() if v}
            return {"mode": "in-memory", "tables": counts}
        return {"mode": "postgresql", "pool_size": self._pool.get_size() if self._pool else 0}


# Singleton
_repo = Repository()


def get_repository() -> Repository:
    return _repo
