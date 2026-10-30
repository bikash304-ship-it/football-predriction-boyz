"""Walk-forward backtest + hyper-parameter tuning on stored historical results.

    DATABASE_URL=... python -m scripts.backtest --league premier-league --start 2025-08-01 [--tune]

Results are printed and stored on the latest model_versions row for that league
(shown on the Analytics page). Uses only matches before each test date — no leakage.
"""
import argparse
import asyncio
import json
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.pool import close_pool, get_pool  # noqa: E402
from app.leagues import BY_SLUG  # noqa: E402
from app.model.backtest import tune, walk_forward  # noqa: E402
from app.services.jobs import _league_history  # noqa: E402


async def main(slug: str, start: date, do_tune: bool):
    pool = await get_pool()
    async with pool.connection() as c:
        lid = (await (await c.execute("SELECT id FROM leagues WHERE slug=%s", (slug,))).fetchone())["id"]
        hist = await _league_history(c, lid)
        st = datetime.combine(start, time(0), tzinfo=timezone.utc)
        result = {"walk_forward": walk_forward(hist, st)}
        if do_tune:
            result["tuning"] = tune(hist, st)
        await c.execute("""UPDATE model_versions SET backtest=%s WHERE id=(SELECT id FROM model_versions
                           WHERE league_id=%s ORDER BY created_at DESC LIMIT 1)""", (json.dumps(result), lid))
    print(json.dumps({k: v for k, v in result["walk_forward"].items() if "reliability" not in k}, indent=2, default=str))
    await close_pool()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", required=True, choices=sorted(BY_SLUG))
    ap.add_argument("--start", required=True, type=date.fromisoformat)
    ap.add_argument("--tune", action="store_true")
    a = ap.parse_args()
    asyncio.run(main(a.league, a.start, a.tune))
