"""Run one or more jobs once and exit — used by the free GitHub Actions schedule.

    python -m app.run_jobs fixtures context predict
    python -m app.run_jobs daily
"""
from __future__ import annotations

import asyncio
import logging
import sys

from .config import settings
from .db.pool import close_pool, migrate
from .services import jobs


async def _failures_since(started) -> list[dict]:
    from .db.pool import get_pool
    pool = await get_pool()
    async with pool.connection() as c:
        return await (await c.execute(
            "SELECT job, left(split_part(error, E'\\n', 1), 400) AS msg FROM sync_logs WHERE started_at >= %s AND ok IS FALSE ORDER BY started_at",
            (started,))).fetchall()


async def main(names: list[str]) -> int:
    from datetime import datetime, timezone
    started = datetime.now(timezone.utc)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if settings.demo_mode:
        logging.error("API_FOOTBALL_KEY and DATABASE_URL must both be set (GitHub → Settings → Secrets → Actions).")
        return 1
    await migrate()
    await jobs.seed_leagues()
    for name in names:
        if name == "daily":
            await jobs.daily_pipeline()
        elif name in jobs.JOBS:
            logging.info("running %s", name)
            await jobs.JOBS[name]()
        else:
            logging.error("unknown job %s (choose from daily, %s)", name, ", ".join(jobs.JOBS))
            return 2
    failed = await _failures_since(started)
    await close_pool()
    for f in failed:
        _gh_error(f"{f['job']}: {f['msg']}")
    return 3 if failed else 0


def _gh_error(msg: str):
    """Surface failures as GitHub annotations (visible on the run page without opening logs)."""
    print("::error::" + msg.replace("\n", " | ")[:900], flush=True)


if __name__ == "__main__":
    try:
        code = asyncio.run(main(sys.argv[1:] or ["fixtures", "context", "predict", "settle"]))
    except Exception as e:  # noqa: BLE001
        _gh_error(f"{type(e).__name__}: {e}")
        raise
    if code in (1, 2):
        _gh_error(f"run_jobs exited with code {code} (check that API_FOOTBALL_KEY and DATABASE_URL secrets are set)")
    raise SystemExit(code)
