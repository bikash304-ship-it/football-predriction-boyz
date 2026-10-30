"""FastAPI service for Football Predriction Boyz.

Run:  uvicorn app.api.main:app --reload --port 8000
Demo mode is automatic when API_FOOTBALL_KEY or DATABASE_URL is missing.
"""
from __future__ import annotations

import asyncio
import inspect
import os
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ..config import settings
from ..model.ranking import MARKET_FILTERS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = FastAPI(title=settings.app_name, description=settings.tagline, version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET", "POST", "PUT", "DELETE"],
                   allow_headers=["*"])


def _repo():
    if settings.demo_mode:
        from ..services.demo import TZ, get_demo_repo
        return get_demo_repo(datetime.now(TZ).date())
    from ..services.live_repo import LiveRepository
    return LiveRepository()


async def _call(fn, *a, **kw):
    """Demo repo is sync (CPU, cached), live repo is async."""
    if inspect.iscoroutinefunction(fn):
        return await fn(*a, **kw)
    return await asyncio.to_thread(fn, *a, **kw)


def _tz(tz: str) -> str:
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(400, f"Unknown timezone '{tz}'")
    return tz


def _day(d: str | None, tz: str) -> date:
    if not d:
        return datetime.now(ZoneInfo(tz)).date()
    try:
        return date.fromisoformat(d)
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")


async def _refresh_live_if_stale(max_age_s: int = 60):
    """Serverless-friendly live scores: when someone is looking and a match is on,
    refresh from the provider at most once per `max_age_s` (shared across instances via the DB)."""
    if settings.demo_mode:
        return
    try:
        from ..db.pool import get_pool
        from ..services.jobs import job_live
        pool = await get_pool()
        async with pool.connection() as c:
            row = await (await c.execute(
                "SELECT max(started_at) > now() - %s * interval '1 second' AS fresh FROM sync_logs WHERE job='live'",
                (max_age_s,))).fetchone()
        if row and row["fresh"]:
            return
        await asyncio.wait_for(job_live(), timeout=8)
    except Exception:  # never fail a page because the live refresh failed; last verified data is served
        logging.getLogger("api").warning("on-demand live refresh failed", exc_info=True)


@app.on_event("startup")
async def startup():
    if settings.demo_mode:
        logging.getLogger("api").warning("DEMO MODE: API_FOOTBALL_KEY/DATABASE_URL not set — serving labelled demo data")
        await asyncio.to_thread(_repo)  # warm the demo build (~5 s)
    else:
        from ..db.pool import migrate
        from ..services.jobs import seed_leagues
        try:
            await migrate()
            await seed_leagues()
        except Exception:
            # Keep serving: requests will report the database problem instead of the whole API crashing.
            logging.getLogger("api").exception("database not reachable at startup")
            return
        # On a single always-on host (e.g. Render) the API process also runs the scheduled jobs.
        if os.getenv("RUN_SCHEDULER", "").lower() in {"1", "true", "yes"}:
            from ..scheduler import start_in_background
            await start_in_background()


@app.get("/api/health")
async def health():
    r = _repo()
    h = await _call(r.health)
    return {**h, "app": settings.app_name, "tagline": settings.tagline, "default_timezone": settings.default_timezone}


@app.get("/api/leagues")
async def leagues():
    return await _call(_repo().leagues)


@app.get("/api/leagues/{slug}")
async def league(slug: str):
    out = await _call(_repo().league, slug)
    if not out:
        raise HTTPException(404, "league not found")
    return out


@app.get("/api/fixtures")
async def fixtures(date: str | None = None, tz: str = "Europe/Oslo", league: str | None = None):
    tz = _tz(tz)
    day = _day(date, tz)
    await _refresh_live_if_stale()
    return {"date": day.isoformat(), "timezone": tz, "fixtures": await _call(_repo().fixtures_on, day, tz, league)}


@app.get("/api/fixtures/week")
async def fixtures_week(tz: str = "Europe/Oslo"):
    tz = _tz(tz)
    today = datetime.now(ZoneInfo(tz)).date()
    return {"start": today.isoformat(), "fixtures": await _call(_repo().fixtures_range, today, 8, tz)}


@app.get("/api/fixtures/live")
async def live():
    await _refresh_live_if_stale()
    return {"fixtures": await _call(_repo().live), "fetched_at": datetime.utcnow().isoformat() + "Z"}


@app.get("/api/fixtures/{fid}")
async def fixture(fid: int):
    await _refresh_live_if_stale()
    out = await _call(_repo().fixture_detail, fid)
    if not out:
        raise HTTPException(404, "fixture not found")
    return out


@app.get("/api/predictions/top")
async def top(date: str | None = None, tz: str = "Europe/Oslo", market: str | None = None, league: str | None = None,
              min_p: float = Query(0.0, ge=0, le=1), limit: int = Query(20, ge=1, le=100)):
    if market and market not in MARKET_FILTERS:
        raise HTTPException(400, f"market must be one of {sorted(MARKET_FILTERS)}")
    tz = _tz(tz)
    return {"items": await _call(_repo().top, _day(date, tz), tz, market, league, min_p, limit)}


@app.get("/api/analytics")
async def analytics():
    return await _call(_repo().analytics)


@app.get("/api/history")
async def history(league: str | None = None, market: str | None = None, limit: int = Query(300, le=1000)):
    return {"items": await _call(_repo().history_rows, league, market, limit)}


@app.get("/api/search")
async def search(q: str = Query(..., min_length=2)):
    return await _call(_repo().search, q)


@app.post("/api/admin/refresh")
async def admin_refresh(job: str = "all", x_admin_token: str | None = Header(None)):
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(401, "admin token required")
    if settings.demo_mode:
        from ..services.demo import TZ, get_demo_repo
        get_demo_repo.cache_clear()
        get_demo_repo(datetime.now(TZ).date())
        return {"ok": True, "demo": True, "ran": ["demo-rebuild"]}
    from ..services.jobs import JOBS, daily_pipeline
    if job == "all":
        asyncio.create_task(daily_pipeline())
        return {"ok": True, "queued": "all"}
    if job not in JOBS:
        raise HTTPException(400, f"job must be 'all' or one of {sorted(JOBS)}")
    asyncio.create_task(JOBS[job]())
    return {"ok": True, "queued": job}
