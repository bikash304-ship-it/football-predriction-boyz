"""Check that YOUR API-Football subscription covers all six leagues before syncing.

    API_FOOTBALL_KEY=... python -m scripts.verify_coverage
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.leagues import LEAGUES  # noqa: E402
from app.providers.api_football import ApiFootballProvider  # noqa: E402
from app.providers.base import ProviderError  # noqa: E402


async def main() -> int:
    p = ApiFootballProvider(settings.api_football_key, settings.api_football_base)
    bad = 0
    print(f"{'League':24} {'ID':>4} {'Season':>6}  fixtures standings injuries lineups stats(xG) odds")
    for l in LEAGUES:
        try:
            c = await p.coverage(l.provider_id)
        except ProviderError as e:
            print(f"{l.name:24} {l.provider_id:>4}  ERROR {e}")
            bad += 1
            continue
        ok = c.name == l.expected_name
        bad += not ok
        flag = lambda b: "yes" if b else " - "
        print(f"{l.name:24} {l.provider_id:>4} {c.current_season or '?':>6}  {flag(c.fixtures):>8} {flag(c.standings):>9} "
              f"{flag(c.injuries):>8} {flag(c.lineups):>7} {flag(c.statistics):>9} {flag(c.odds):>4}"
              + ("" if ok else f"   <-- provider returned '{c.name}' ({c.country})"))
    await p.close()
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
