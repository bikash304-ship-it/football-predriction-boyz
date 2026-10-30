"""API-Football v3 adapter (https://www.api-football.com/documentation-v3).

Server-side only. Includes a token-bucket rate limiter, retries with exponential
backoff, a short in-process TTL cache and structured error logging.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timezone
from typing import Any

import httpx

from .base import (FixtureDTO, FootballProvider, InjuryDTO, LeagueCoverage, MatchStatsDTO, OddsDTO,
                   ProviderError, StandingDTO, TeamDTO)

log = logging.getLogger("provider.api_football")

STATUS_MAP = {"LIVE": "1H", "BT": "ET"}  # normalise the few codes we don't treat separately


class _RateLimiter:
    def __init__(self, per_minute: int):
        self.capacity = max(per_minute, 1)
        self.tokens = float(self.capacity)
        self.rate = self.capacity / 60.0
        self.updated = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            while True:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
                self.updated = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                await asyncio.sleep((1 - self.tokens) / self.rate)


class ApiFootballProvider(FootballProvider):
    name = "api-football"

    def __init__(self, api_key: str, base_url: str = "https://v3.football.api-sports.io",
                 requests_per_minute: int = 250, cache_ttl: int = 30):
        if not api_key:
            raise ProviderError("API_FOOTBALL_KEY is not set")
        self._client = httpx.AsyncClient(base_url=base_url, headers={"x-apisports-key": api_key}, timeout=20)
        self._limiter = _RateLimiter(requests_per_minute)
        self._cache: dict[str, tuple[float, Any]] = {}
        self._ttl = cache_ttl

    async def close(self):
        await self._client.aclose()

    async def _get(self, path: str, params: dict, ttl: int | None = None) -> list[dict]:
        key = path + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params))
        ttl = self._ttl if ttl is None else ttl
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < ttl:
            return hit[1]
        delay = 1.0
        for attempt in range(4):
            await self._limiter.acquire()
            try:
                r = await self._client.get(path, params=params)
                if r.status_code == 429 or r.status_code >= 500:
                    raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
                r.raise_for_status()
                body = r.json()
                errors = body.get("errors")
                if errors:
                    # API-Football returns 200 with an `errors` object for plan/quota problems.
                    raise ProviderError(f"API-Football error on {path}: {errors}")
                data = body.get("response", [])
                self._cache[key] = (time.monotonic(), data)
                return data
            except ProviderError:
                log.error("provider_error path=%s params=%s", path, params)
                raise
            except (httpx.HTTPError, ValueError) as e:
                log.warning("request_failed path=%s attempt=%d err=%s", path, attempt + 1, e)
                if attempt == 3:
                    raise ProviderError(f"{path} failed after retries: {e}") from e
                await asyncio.sleep(delay)
                delay *= 2
        return []

    # ------------------------------------------------------------------ parsing
    @staticmethod
    def _team(t: dict) -> TeamDTO:
        return TeamDTO(provider_id=t["id"], name=t["name"], logo_url=t.get("logo"))

    @classmethod
    def _fixture(cls, f: dict) -> FixtureDTO:
        fx, lg, teams, goals, score = f["fixture"], f["league"], f["teams"], f["goals"], f.get("score", {})
        st = fx["status"]["short"]
        ft = score.get("fulltime") or {}
        status = STATUS_MAP.get(st, st)
        final = status in {"FT", "AET", "PEN"}
        return FixtureDTO(
            provider_id=fx["id"], league_provider_id=lg["id"], season=lg["season"],
            kickoff_utc=datetime.fromtimestamp(fx["timestamp"], tz=timezone.utc),
            status=status, status_long=fx["status"]["long"], elapsed=fx["status"].get("elapsed"),
            home=cls._team(teams["home"]), away=cls._team(teams["away"]),
            venue=(fx.get("venue") or {}).get("name"), city=(fx.get("venue") or {}).get("city"),
            round=lg.get("round"), goals_home=goals.get("home"), goals_away=goals.get("away"),
            # `score.fulltime` is the 90-minute score; fall back to goals only when the match ended in regulation.
            ft_home=ft.get("home") if ft.get("home") is not None else (goals.get("home") if final and status == "FT" else None),
            ft_away=ft.get("away") if ft.get("away") is not None else (goals.get("away") if final and status == "FT" else None),
            raw=f,
        )

    # ------------------------------------------------------------------ endpoints
    async def coverage(self, league_id: int) -> LeagueCoverage:
        data = await self._get("/leagues", {"id": league_id, "current": "true"}, ttl=3600)
        if not data:
            raise ProviderError(f"League {league_id} not available on this subscription")
        d = data[0]
        season = next((s for s in d["seasons"] if s.get("current")), d["seasons"][-1])
        cov = season.get("coverage", {})
        fx = cov.get("fixtures", {})
        return LeagueCoverage(
            provider_id=league_id, name=d["league"]["name"], country=d["country"]["name"],
            current_season=season.get("year"), fixtures=True,
            standings=bool(cov.get("standings")), injuries=bool(cov.get("injuries")),
            lineups=bool(fx.get("lineups")), statistics=bool(fx.get("statistics_fixtures")),
            odds=bool(cov.get("odds")),
        )

    async def fixtures(self, league_id: int, season: int, date_from: date, date_to: date) -> list[FixtureDTO]:
        data = await self._get("/fixtures", {"league": league_id, "season": season, "from": date_from.isoformat(),
                                             "to": date_to.isoformat(), "timezone": "UTC"}, ttl=600)
        return [self._fixture(f) for f in data]

    async def season_fixtures(self, league_id: int, season: int) -> list[FixtureDTO]:
        data = await self._get("/fixtures", {"league": league_id, "season": season, "timezone": "UTC"}, ttl=3600)
        return [self._fixture(f) for f in data]

    async def live_fixtures(self, league_ids: list[int]) -> list[FixtureDTO]:
        data = await self._get("/fixtures", {"live": "-".join(map(str, league_ids))}, ttl=20)
        return [self._fixture(f) for f in data]

    async def fixture(self, fixture_id: int) -> FixtureDTO | None:
        data = await self._get("/fixtures", {"id": fixture_id}, ttl=20)
        return self._fixture(data[0]) if data else None

    async def standings(self, league_id: int, season: int) -> list[StandingDTO]:
        data = await self._get("/standings", {"league": league_id, "season": season}, ttl=900)
        out: list[StandingDTO] = []
        for block in data:
            for group in block["league"]["standings"]:
                for row in group:
                    a = row["all"]
                    out.append(StandingDTO(
                        team_provider_id=row["team"]["id"], rank=row["rank"], points=row["points"],
                        played=a["played"], won=a["win"], drawn=a["draw"], lost=a["lose"],
                        goals_for=a["goals"]["for"], goals_against=a["goals"]["against"],
                        form=row.get("form"), group=row.get("group"),
                    ))
        return out

    async def injuries(self, fixture_id: int) -> list[InjuryDTO]:
        data = await self._get("/injuries", {"fixture": fixture_id}, ttl=900)
        return [InjuryDTO(team_provider_id=i["team"]["id"], player=i["player"]["name"],
                          type=i["player"].get("type", ""), reason=i["player"].get("reason")) for i in data]

    async def lineups(self, fixture_id: int) -> dict | None:
        data = await self._get("/fixtures/lineups", {"fixture": fixture_id}, ttl=300)
        if len(data) != 2:
            return None
        return {str(t["team"]["id"]): {"formation": t.get("formation"),
                                       "start_xi": [p["player"]["name"] for p in t.get("startXI", [])]} for t in data}

    async def match_stats(self, fixture_id: int) -> MatchStatsDTO | None:
        data = await self._get("/fixtures/statistics", {"fixture": fixture_id}, ttl=3600)
        if len(data) != 2:
            return None
        parsed, xg = {}, []
        for t in data:
            s = {x["type"]: x["value"] for x in t["statistics"]}
            parsed[str(t["team"]["id"])] = s
            v = s.get("expected_goals")
            xg.append(float(v) if v not in (None, "") else None)
        return MatchStatsDTO(fixture_id, xg[0], xg[1], parsed)

    async def odds(self, fixture_id: int) -> list[OddsDTO]:
        data = await self._get("/odds", {"fixture": fixture_id}, ttl=900)
        out: list[OddsDTO] = []
        now = datetime.now(timezone.utc)
        name_map = {"Match Winner": "1X2", "Both Teams Score": "BTTS", "Goals Over/Under": "OU"}
        sel_map = {"Home": "1", "Draw": "X", "Away": "2"}
        for item in data:
            for bk in item.get("bookmakers", [])[:1]:  # first bookmaker only; configure as needed
                for bet in bk.get("bets", []):
                    kind = name_map.get(bet["name"])
                    if not kind:
                        continue
                    if kind == "OU":
                        lines: dict[str, dict[str, float]] = {}
                        for v in bet["values"]:
                            side, line = v["value"].split(" ")
                            lines.setdefault(line, {})[side] = float(v["odd"])
                        for line, sel in lines.items():
                            out.append(OddsDTO(fixture_id, bk["name"], f"OU{line}", sel, now))
                    else:
                        out.append(OddsDTO(fixture_id, bk["name"], kind,
                                           {sel_map.get(v["value"], v["value"]): float(v["odd"]) for v in bet["values"]}, now))
        return out
