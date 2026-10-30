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


async def main(names: list[str]) -> int:
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
    await close_pool()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:] or ["fixtures", "context", "predict", "settle"])))
