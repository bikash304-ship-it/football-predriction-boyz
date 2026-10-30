"""PostgreSQL connection pool + a tiny ordered SQL migration runner."""
from __future__ import annotations

import logging
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from ..config import settings

log = logging.getLogger("db")
MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
_pool: AsyncConnectionPool | None = None


async def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(settings.database_url, min_size=1, max_size=10, open=False,
                                    kwargs={"row_factory": dict_row, "autocommit": True})
        await _pool.open()
    return _pool


async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def migrate() -> list[str]:
    """Apply migrations/NNN_*.sql in order, each exactly once, inside a transaction."""
    pool = await get_pool()
    applied: list[str] = []
    async with pool.connection() as conn:
        await conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
        done = {r["name"] for r in await (await conn.execute("SELECT name FROM schema_migrations")).fetchall()}
        for f in sorted(MIGRATIONS.glob("*.sql")):
            if f.name in done:
                continue
            async with conn.transaction():
                await conn.execute(f.read_text())
                await conn.execute("INSERT INTO schema_migrations(name) VALUES (%s)", (f.name,))
            log.info("applied migration %s", f.name)
            applied.append(f.name)
    return applied
