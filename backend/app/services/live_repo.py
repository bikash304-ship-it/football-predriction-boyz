"""Read-side repository for live mode (PostgreSQL). Mirrors DemoRepository's interface."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..db.pool import get_pool
from ..leagues import BY_SLUG, LEAGUES
from ..model.ranking import calibration_errors, summarize_settled, top_predictions
from .serialize import LIVE_STATUSES, fixture_out

FIXTURE_SELECT = """
SELECT f.*, l.slug AS league_slug,
       th.name AS home_name, th.logo_url AS home_logo, ta.name AS away_name, ta.logo_url AS away_logo,
       lp.payload AS prediction
FROM fixtures f
JOIN leagues l ON l.id = f.league_id
JOIN teams th ON th.id = f.home_team_id
JOIN teams ta ON ta.id = f.away_team_id
LEFT JOIN LATERAL (
    SELECT payload FROM predictions p
    WHERE p.fixture_id = f.id AND p.created_at < f.kickoff_utc
    ORDER BY p.created_at DESC LIMIT 1
) lp ON TRUE
"""


def _initials(name: str) -> str:
    return "".join(w[0] for w in name.split() if w[:1].isalpha())[:3].upper()


def _row_out(r: dict) -> dict:
    return fixture_out(
        id=r["id"], league=BY_SLUG[r["league_slug"]], kickoff_utc=r["kickoff_utc"], status=r["status"],
        status_long=r["status_long"] or r["status"], elapsed=r["elapsed"],
        home={"id": r["home_team_id"], "name": r["home_name"], "logo": r["home_logo"], "initials": _initials(r["home_name"])},
        away={"id": r["away_team_id"], "name": r["away_name"], "logo": r["away_logo"], "initials": _initials(r["away_name"])},
        venue=r["venue"], city=r["city"], round=r["round"], goals=(r["goals_home"], r["goals_away"]),
        ft=(r["ft_home"], r["ft_away"]), demo=False, prediction=r["prediction"])


class LiveRepository:
    demo = False

    async def _all(self, sql: str, args: tuple = ()) -> list[dict]:
        pool = await get_pool()
        async with pool.connection() as c:
            return await (await c.execute(sql, args)).fetchall()

    async def health(self) -> dict:
        rows = await self._all("""SELECT DISTINCT ON (job) job, started_at, finished_at, ok, error
                                  FROM sync_logs ORDER BY job, started_at DESC""")
        last_ok = await self._all("""SELECT job, max(finished_at) AS at FROM sync_logs WHERE ok GROUP BY job""")
        warnings = [f"Last '{r['job']}' sync failed at {r['started_at'].isoformat()} — showing last verified data."
                    for r in rows if r["ok"] is False]
        return {"demo": False, "provider": "api-football", "live_data_configured": True,
                "last_sync": {r["job"]: r["at"].isoformat() if r["at"] else None for r in last_ok}, "warnings": warnings}

    async def leagues(self) -> list[dict]:
        rows = await self._all("""SELECT l.slug, l.logo_url, l.coverage,
                                         count(f.id) FILTER (WHERE (f.kickoff_utc AT TIME ZONE 'Europe/Oslo')::date
                                                                   = (now() AT TIME ZONE 'Europe/Oslo')::date) AS today
                                  FROM leagues l LEFT JOIN fixtures f ON f.league_id=l.id GROUP BY l.id""")
        by = {r["slug"]: r for r in rows}
        return [{"slug": l.slug, "name": l.name, "country": l.country, "country_code": l.country_code,
                 "logo": by.get(l.slug, {}).get("logo_url"), "today": by.get(l.slug, {}).get("today", 0),
                 "coverage": by.get(l.slug, {}).get("coverage"), "demo": False} for l in LEAGUES]

    async def league(self, slug: str) -> dict | None:
        if slug not in BY_SLUG:
            return None
        fx = await self._all(FIXTURE_SELECT + " WHERE l.slug=%s AND f.kickoff_utc BETWEEN now()-interval '14 days' AND now()+interval '8 days' ORDER BY f.kickoff_utc", (slug,))
        st = await self._all("""SELECT s.*, t.name AS team, t.logo_url AS logo FROM standings s JOIN leagues l ON l.id=s.league_id
                                JOIN teams t ON t.id=s.team_id WHERE l.slug=%s
                                AND s.season_year=(SELECT max(season_year) FROM standings s2 WHERE s2.league_id=l.id)
                                ORDER BY s.group_name NULLS FIRST, s.rank""", (slug,))
        league = next(l for l in await self.leagues() if l["slug"] == slug)
        return {"league": league, "standings": [{**s, "initials": _initials(s["team"]), "updated_at": s["updated_at"].isoformat()} for s in st],
                "fixtures": [_row_out(r) for r in fx], "demo": False}

    async def fixtures_on(self, day: date, tz: str = "Europe/Oslo", league: str | None = None) -> list[dict]:
        z = ZoneInfo(tz)
        start = datetime.combine(day, datetime.min.time(), tzinfo=z)
        end = start + timedelta(days=1)
        sql = FIXTURE_SELECT + " WHERE f.kickoff_utc >= %s AND f.kickoff_utc < %s" + (" AND l.slug=%s" if league else "") + " ORDER BY f.kickoff_utc"
        args = (start, end, league) if league else (start, end)
        return [_row_out(r) for r in await self._all(sql, args)]

    async def fixtures_range(self, start: date, days: int, tz: str = "Europe/Oslo") -> list[dict]:
        z = ZoneInfo(tz)
        s = datetime.combine(start, datetime.min.time(), tzinfo=z)
        rows = await self._all(FIXTURE_SELECT + " WHERE f.kickoff_utc >= %s AND f.kickoff_utc < %s ORDER BY f.kickoff_utc",
                               (s, s + timedelta(days=days)))
        return [_row_out(r) for r in rows]

    async def live(self) -> list[dict]:
        return [_row_out(r) for r in await self._all(FIXTURE_SELECT + " WHERE f.status = ANY(%s) ORDER BY f.kickoff_utc",
                                                     (list(LIVE_STATUSES),))]

    async def fixture_detail(self, fid: int) -> dict | None:
        rows = await self._all(FIXTURE_SELECT + " WHERE f.id=%s", (fid,))
        if not rows:
            return None
        r = rows[0]
        hist = await self._all("""SELECT p.id, p.created_at, p.p_home, p.p_draw, p.p_away, p.model_version, p.input_freshness
                                  FROM predictions p WHERE p.fixture_id=%s AND p.created_at < %s ORDER BY p.created_at""",
                               (fid, r["kickoff_utc"]))
        expl = None
        if hist:
            e = await self._all("SELECT explanation FROM prediction_explanations WHERE prediction_id=%s", (hist[-1]["id"],))
            expl = e[0]["explanation"] if e else None
        settle = await self._all("SELECT market, selection, probability, outcome FROM prediction_settlements WHERE prediction_id=%s",
                                 (hist[-1]["id"],)) if hist else []
        league = await self.league(r["league_slug"])
        return {"fixture": _row_out(r), "prediction": r["prediction"], "explanation": expl,
                "standings": league["standings"] if league else [], "settlement": settle or None,
                "prediction_history": [{"created_at": h["created_at"].isoformat(), "home": round(h["p_home"] * 100),
                                        "draw": round(h["p_draw"] * 100), "away": round(h["p_away"] * 100),
                                        "model_version": h["model_version"]} for h in hist],
                "freshness": hist[-1]["input_freshness"] if hist else None, "demo": False}

    async def _settled(self, days: int = 365) -> list[dict]:
        return await self._all("""SELECT s.*, l.slug AS league_slug, f.id AS fixture_id, f.kickoff_utc,
                                         th.name AS home, ta.name AS away
                                  FROM prediction_settlements s JOIN predictions p ON p.id=s.prediction_id
                                  JOIN fixtures f ON f.id=p.fixture_id JOIN leagues l ON l.id=f.league_id
                                  JOIN teams th ON th.id=f.home_team_id JOIN teams ta ON ta.id=f.away_team_id
                                  WHERE s.settled_at > now() - %s * interval '1 day'""", (days,))

    async def top(self, day: date, tz: str = "Europe/Oslo", market: str | None = None, league: str | None = None,
                  min_p: float = 0.0, limit: int = 20) -> list[dict]:
        fx = await self.fixtures_on(day, tz, league)
        rows = await self._all(FIXTURE_SELECT + " WHERE f.id = ANY(%s)", ([f["id"] for f in fx],)) if fx else []
        payload = {r["id"]: r["prediction"] for r in rows if r["prediction"]}
        items = [{"fixture": f, "prediction": payload[f["id"]]} for f in fx if f["id"] in payload and f["status"] in ("NS", "TBD")]
        calib = calibration_errors(await self._settled(180))
        return top_predictions(items, market=market, min_p=min_p, calib=calib, limit=limit)

    async def analytics(self) -> dict:
        s = summarize_settled(await self._settled(365), datetime.now(timezone.utc))
        s["demo"] = False
        backtests = await self._all("""SELECT DISTINCT ON (league_id) l.slug, mv.backtest, mv.created_at
                                       FROM model_versions mv JOIN leagues l ON l.id=mv.league_id
                                       WHERE mv.backtest IS NOT NULL ORDER BY league_id, mv.created_at DESC""")
        s["backtests"] = {b["slug"]: b["backtest"] for b in backtests}
        return s

    async def history_rows(self, league: str | None = None, market: str | None = None, limit: int = 300) -> list[dict]:
        rows = await self._settled(365)
        rows = [r for r in rows if (not league or r["league_slug"] == league) and (not market or r["market"] == market)]
        rows.sort(key=lambda r: r["settled_at"], reverse=True)
        return [{"fixture_id": r["fixture_id"], "league_slug": r["league_slug"], "market": r["market"],
                 "selection": r["selection"], "probability": r["probability"], "p": r["probability"], "outcome": r["outcome"],
                 "home": r["home"], "away": r["away"], "final": [r["final_home"], r["final_away"]],
                 "settled_at": r["settled_at"].isoformat(), "kickoff_utc": r["kickoff_utc"].isoformat(), "demo": False}
                for r in rows[:limit]]

    async def search(self, q: str) -> dict:
        like = f"%{q.lower().strip()}%"
        teams = await self._all("SELECT id, name, logo_url AS logo FROM teams WHERE lower(name) LIKE %s ORDER BY name LIMIT 10", (like,))
        ids = [t["id"] for t in teams]
        fx = await self._all(FIXTURE_SELECT + """ WHERE (f.home_team_id = ANY(%s) OR f.away_team_id = ANY(%s))
                                                  AND f.kickoff_utc > now() - interval '7 days' ORDER BY f.kickoff_utc LIMIT 20""",
                             (ids, ids)) if ids else []
        return {"teams": [{**t, "initials": _initials(t["name"])} for t in teams], "fixtures": [_row_out(r) for r in fx], "demo": False}
