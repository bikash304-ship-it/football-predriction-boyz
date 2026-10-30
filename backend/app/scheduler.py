"""Background worker — runs on the server, independent of anyone opening the website.

Run:  python -m app.scheduler
Timings (UTC):
  fixtures  every hour at :05
  live      every 45 s (no API calls unless a match is live or about to start)
  context   every 15 min (injuries 48h out, lineups ~75 min before kickoff)
  predict   every 30 min (appends only when probabilities/context changed materially)
  settle    every 10 min
  odds      every 2 h (only if ODDS_ENABLED=true)
  daily     04:15 coverage -> fixtures -> history/standings/xG -> context -> predict -> settle
"""
from __future__ import annotations

import asyncio
import logging
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .config import settings
from .db.pool import close_pool, migrate
from .services import jobs

log = logging.getLogger("scheduler")


def build_scheduler() -> AsyncIOScheduler:
    s = AsyncIOScheduler(timezone="UTC", job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 120})
    s.add_job(jobs.job_fixtures, CronTrigger(minute=5), id="fixtures")
    s.add_job(jobs.job_live, IntervalTrigger(seconds=45), id="live")
    s.add_job(jobs.job_context, IntervalTrigger(minutes=15), id="context")
    s.add_job(jobs.job_predict, IntervalTrigger(minutes=30), id="predict")
    s.add_job(jobs.job_settle, IntervalTrigger(minutes=10), id="settle")
    s.add_job(jobs.job_odds, IntervalTrigger(hours=2), id="odds")
    s.add_job(jobs.daily_pipeline, CronTrigger(hour=4, minute=15), id="daily")
    return s


_running: AsyncIOScheduler | None = None


async def start_in_background():
    """Start the jobs inside an already-running event loop (the API process)."""
    global _running
    if _running is not None:
        return
    _running = build_scheduler()
    _running.start()
    asyncio.get_running_loop().create_task(jobs.daily_pipeline())  # warm start without blocking startup
    log.info("scheduler started in API process with %d jobs", len(_running.get_jobs()))


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if settings.demo_mode:
        log.error("Live data is not configured (API_FOOTBALL_KEY and DATABASE_URL). The scheduler only runs in live mode.")
        return
    await migrate()
    await jobs.seed_leagues()
    await jobs.daily_pipeline()  # warm start
    s = build_scheduler()
    s.start()
    log.info("scheduler started with %d jobs", len(s.get_jobs()))

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    await stop.wait()
    s.shutdown(wait=False)
    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
