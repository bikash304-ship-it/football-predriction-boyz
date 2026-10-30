"""Background jobs for live mode. Each job is idempotent and writes a sync_logs row.

Workflow (see scheduler.py for timings):
 1 coverage   – verify the subscription covers each league; resolve current season
 2 fixtures   – upsert fixtures for yesterday .. +8 days (hourly)
 3 history    – upsert full current + previous seasons, standings, xG (nightly)
 4 context    – injuries/lineups for matches kicking off soon (every 15 min)
 5 predict    – refit per league, append predictions that changed materially
 6 live       – live scores every 45 s while matches are in progress
 7 settle     – settle official pre-match predictions after final whistle
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from ..config import settings
from ..db.pool import get_pool
from ..leagues import LEAGUES
from ..model.dixon_coles import FitConfig, InsufficientDataError, MatchResult, fit
from ..model.explain import build_explanation, llm_polish
from ..model.predictor import MODEL_VERSION, ContextAvailability, predict_fixture
from ..model.settlement import VOID_STATUSES, FinalScore, Outcome, settle_pick
from ..providers.api_football import ApiFootballProvider
from ..providers.base import FixtureDTO, ProviderError
from .serialize import FINAL_STATUSES, LIVE_STATUSES

log = logging.getLogger("jobs")
_provider: ApiFootballProvider | None = None


def provider() -> ApiFootballProvider:
    global _provider
    if _provider is None:
        _provider = ApiFootballProvider(settings.api_football_key, settings.api_football_base,
                                        settings.api_requests_per_minute)
    return _provider


@asynccontextmanager
async def job_log(name: str):
    pool = await get_pool()
    started = datetime.now(timezone.utc)
    state = {"items": 0, "details": {}}
    async with pool.connection() as c:
        row = await (await c.execute("INSERT INTO sync_logs(job, started_at) VALUES (%s,%s) RETURNING id",
                                     (name, started))).fetchone()
    try:
        yield state
        ok, err = True, None
    except Exception as e:  # logged, never swallowed silently
        ok, err = False, f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=4)}"
        log.exception("job %s failed", name)
    async with pool.connection() as c:
        await c.execute("UPDATE sync_logs SET finished_at=now(), ok=%s, items=%s, error=%s, details=%s WHERE id=%s",
                        (ok, state["items"], err, json.dumps(state["details"], default=str), row["id"]))


# ---------------------------------------------------------------------- upserts
async def _league_ids(c) -> dict[int, int]:
    rows = await (await c.execute("SELECT id, provider_id FROM leagues")).fetchall()
    return {r["provider_id"]: r["id"] for r in rows}


async def _upsert_team(c, t) -> int:
    r = await (await c.execute(
        """INSERT INTO teams(provider_id, name, logo_url) VALUES (%s,%s,%s)
           ON CONFLICT (provider, provider_id) DO UPDATE SET name=EXCLUDED.name, logo_url=COALESCE(EXCLUDED.logo_url, teams.logo_url)
           RETURNING id""", (t.provider_id, t.name, t.logo_url))).fetchone()
    return r["id"]


async def _upsert_fixture(c, f: FixtureDTO, league_db_id: int) -> int:
    h = await _upsert_team(c, f.home)
    a = await _upsert_team(c, f.away)
    r = await (await c.execute(
        """INSERT INTO fixtures(provider_id, league_id, season_year, round, kickoff_utc, status, status_long, elapsed,
                                home_team_id, away_team_id, venue, city, goals_home, goals_away, ft_home, ft_away, updated_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
           ON CONFLICT (provider, provider_id) DO UPDATE SET
             round=EXCLUDED.round, kickoff_utc=EXCLUDED.kickoff_utc, status=EXCLUDED.status, status_long=EXCLUDED.status_long,
             elapsed=EXCLUDED.elapsed, venue=EXCLUDED.venue, city=EXCLUDED.city, goals_home=EXCLUDED.goals_home,
             goals_away=EXCLUDED.goals_away, ft_home=EXCLUDED.ft_home, ft_away=EXCLUDED.ft_away, updated_at=now()
           RETURNING id""",
        (f.provider_id, league_db_id, f.season, f.round, f.kickoff_utc, f.status, f.status_long, f.elapsed,
         h, a, f.venue, f.city, f.goals_home, f.goals_away, f.ft_home, f.ft_away))).fetchone()
    return r["id"]


_FIXTURE_UPSERT = """INSERT INTO fixtures(provider_id, league_id, season_year, round, kickoff_utc, status, status_long, elapsed,
                                home_team_id, away_team_id, venue, city, goals_home, goals_away, ft_home, ft_away, updated_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
           ON CONFLICT (provider, provider_id) DO UPDATE SET
             round=EXCLUDED.round, kickoff_utc=EXCLUDED.kickoff_utc, status=EXCLUDED.status, status_long=EXCLUDED.status_long,
             elapsed=EXCLUDED.elapsed, venue=EXCLUDED.venue, city=EXCLUDED.city, goals_home=EXCLUDED.goals_home,
             goals_away=EXCLUDED.goals_away, ft_home=EXCLUDED.ft_home, ft_away=EXCLUDED.ft_away, updated_at=now()"""


async def _bulk_upsert_fixtures(c, fixtures: list[FixtureDTO], league_db_id: int) -> int:
    """Batched upsert (psycopg pipelines executemany), so hundreds of rows cost a few round-trips."""
    if not fixtures:
        return 0
    teams = {}
    for f in fixtures:
        teams[f.home.provider_id] = f.home
        teams[f.away.provider_id] = f.away
    async with c.cursor() as cur:
        await cur.executemany(
            """INSERT INTO teams(provider_id, name, logo_url) VALUES (%s,%s,%s)
               ON CONFLICT (provider, provider_id) DO UPDATE SET name=EXCLUDED.name,
                 logo_url=COALESCE(EXCLUDED.logo_url, teams.logo_url)""",
            [(t.provider_id, t.name, t.logo_url) for t in teams.values()])
        rows = await (await c.execute("SELECT id, provider_id FROM teams WHERE provider='api-football' AND provider_id = ANY(%s)",
                                      (list(teams),))).fetchall()
        tid = {r["provider_id"]: r["id"] for r in rows}
        await cur.executemany(_FIXTURE_UPSERT, [
            (f.provider_id, league_db_id, f.season, f.round, f.kickoff_utc, f.status, f.status_long, f.elapsed,
             tid[f.home.provider_id], tid[f.away.provider_id], f.venue, f.city, f.goals_home, f.goals_away, f.ft_home, f.ft_away)
            for f in fixtures])
    return len(fixtures)


async def _current_seasons(c) -> dict[int, int]:
    rows = await (await c.execute("SELECT league_id, year FROM seasons WHERE is_current")).fetchall()
    return {r["league_id"]: r["year"] for r in rows}


# ---------------------------------------------------------------------- jobs
async def seed_leagues():
    pool = await get_pool()
    async with pool.connection() as c:
        for l in LEAGUES:
            await c.execute(
                """INSERT INTO leagues(slug, name, country, country_code, provider_id) VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (slug) DO UPDATE SET name=EXCLUDED.name, provider_id=EXCLUDED.provider_id""",
                (l.slug, l.name, l.country, l.country_code, l.provider_id))


async def job_coverage():
    async with job_log("coverage") as st:
        pool = await get_pool()
        async with pool.connection() as c:
            ids = await _league_ids(c)
            for l in LEAGUES:
                cov = await provider().coverage(l.provider_id)
                if cov.name != l.expected_name:
                    raise ProviderError(f"League id {l.provider_id} returned '{cov.name}', expected '{l.expected_name}'")
                await c.execute("UPDATE leagues SET coverage=%s, coverage_checked_at=now() WHERE id=%s",
                                (json.dumps(cov.__dict__), ids[l.provider_id]))
                if cov.current_season:
                    await c.execute("UPDATE seasons SET is_current=FALSE WHERE league_id=%s", (ids[l.provider_id],))
                    await c.execute("""INSERT INTO seasons(league_id, year, is_current) VALUES (%s,%s,TRUE)
                                       ON CONFLICT (league_id, year) DO UPDATE SET is_current=TRUE""",
                                    (ids[l.provider_id], cov.current_season))
                st["details"][l.slug] = cov.__dict__
                st["items"] += 1


async def job_fixtures():
    async with job_log("fixtures") as st:
        pool = await get_pool()
        today = datetime.now(timezone.utc).date()
        async with pool.connection() as c:
            ids, seasons = await _league_ids(c), await _current_seasons(c)
            for l in LEAGUES:
                lid = ids[l.provider_id]
                if lid not in seasons:
                    st["details"][l.slug] = "no current season (run coverage)"
                    continue
                fx = await provider().fixtures(l.provider_id, seasons[lid], today - timedelta(days=1), today + timedelta(days=8))
                await _bulk_upsert_fixtures(c, fx, lid)
                st["items"] += len(fx)
                st["details"][l.slug] = len(fx)


async def job_history():
    """Nightly: full season fixtures for current + previous seasons, standings, and xG for new results.
    Each league is handled independently, so one league's problem doesn't stop the others."""
    async with job_log("history") as st:
        pool = await get_pool()
        errors = []
        async with pool.connection() as c:
            ids, seasons = await _league_ids(c), await _current_seasons(c)
            for l in LEAGUES:
                lid = ids[l.provider_id]
                if lid not in seasons:
                    continue
                try:
                    st["details"][l.slug] = await _league_history_sync(c, l, lid, seasons[lid])
                    st["items"] += st["details"][l.slug]["fixtures"]
                except Exception as e:  # keep going with the other leagues
                    log.exception("history failed for %s", l.slug)
                    errors.append(f"{l.slug}: {type(e).__name__}: {e}")
                    st["details"][l.slug] = {"error": str(e)[:300]}
        if errors:
            raise RuntimeError("; ".join(errors))


async def _league_history_sync(c, l, lid: int, cur: int) -> dict:
    out = {"fixtures": 0, "seasons_skipped": [], "standings": 0, "xg": 0}
    first = cur - settings.history_seasons + 1
    for yr in range(first, cur + 1):
        if yr < cur:
            # Finished past seasons only need downloading once.
            done = await (await c.execute(
                """SELECT count(*) FILTER (WHERE status IN ('FT','AET','PEN','PST','CANC','ABD','AWD','WO')) AS fin, count(*) AS n
                   FROM fixtures WHERE league_id=%s AND season_year=%s""", (lid, yr))).fetchone()
            if done["n"] > 50 and done["fin"] >= done["n"] * 0.98:
                out["seasons_skipped"].append(yr)
                continue
        out["fixtures"] += await _bulk_upsert_fixtures(c, await provider().season_fixtures(l.provider_id, yr), lid)
    await c.execute("INSERT INTO seasons(league_id, year) SELECT %s::int, g FROM generate_series(%s::int, %s::int) g ON CONFLICT DO NOTHING",
                    (lid, first, cur))
    rows = await provider().standings(l.provider_id, cur)
    if rows:
        tmap = {r["provider_id"]: r["id"] for r in await (await c.execute(
            "SELECT id, provider_id FROM teams WHERE provider='api-football' AND provider_id = ANY(%s)",
            ([s.team_provider_id for s in rows],))).fetchall()}
        params = [(lid, cur, tmap[s.team_provider_id], s.rank, s.points, s.played, s.won, s.drawn, s.lost, s.goals_for,
                   s.goals_against, s.form, s.group) for s in rows if s.team_provider_id in tmap]
        async with c.cursor() as cu:
            await cu.executemany(
                """INSERT INTO standings(league_id, season_year, team_id, rank, points, played, won, drawn, lost,
                                         goals_for, goals_against, form, group_name, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                   ON CONFLICT (league_id, season_year, team_id) DO UPDATE SET rank=EXCLUDED.rank, points=EXCLUDED.points,
                     played=EXCLUDED.played, won=EXCLUDED.won, drawn=EXCLUDED.drawn, lost=EXCLUDED.lost,
                     goals_for=EXCLUDED.goals_for, goals_against=EXCLUDED.goals_against, form=EXCLUDED.form,
                     group_name=EXCLUDED.group_name, updated_at=now()""", params)
        out["standings"] = len(params)
    cov = await (await c.execute("SELECT coverage FROM leagues WHERE id=%s", (lid,))).fetchone()
    if (cov["coverage"] or {}).get("statistics"):
        missing = await (await c.execute(
            """SELECT f.id, f.provider_id FROM fixtures f LEFT JOIN match_statistics m ON m.fixture_id=f.id
               WHERE f.league_id=%s AND f.status IN ('FT','AET','PEN') AND m.fixture_id IS NULL
               ORDER BY f.kickoff_utc DESC LIMIT 60""", (lid,))).fetchall()
        for r in missing:
            ms = await provider().match_stats(r["provider_id"])
            # Store a row even without xG so the same match isn't re-requested every night.
            await c.execute("INSERT INTO match_statistics(fixture_id, home_xg, away_xg, stats) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                            (r["id"], ms.home_xg if ms else None, ms.away_xg if ms else None, json.dumps(ms.stats if ms else {})))
            out["xg"] += 1
    return out


async def job_context():
    """Injuries (when covered) for the next 48h; lineups for kickoffs within 75 minutes."""
    async with job_log("context") as st:
        pool = await get_pool()
        async with pool.connection() as c:
            rows = await (await c.execute(
                # Quota-aware: injuries at most every 6 h (hourly in the last 3 h), lineups only near kickoff until found.
                """SELECT f.id, f.provider_id, f.kickoff_utc, l.coverage FROM fixtures f JOIN leagues l ON l.id=f.league_id
                   LEFT JOIN fixture_context fc ON fc.fixture_id=f.id
                   WHERE f.status IN ('NS','TBD') AND f.kickoff_utc BETWEEN now() AND now() + interval '48 hours'
                     AND (fc.injuries_checked_at IS NULL
                          OR fc.injuries_checked_at < now() - interval '6 hours'
                          OR (f.kickoff_utc < now() + interval '3 hours' AND fc.injuries_checked_at < now() - interval '1 hour')
                          OR (f.kickoff_utc < now() + interval '75 minutes' AND fc.lineups IS NULL))""")).fetchall()
            for r in rows:
                cov = r["coverage"] or {}
                inj = lin = None
                if cov.get("injuries"):
                    inj = [i.__dict__ for i in await provider().injuries(r["provider_id"])]
                if cov.get("lineups") and r["kickoff_utc"] - datetime.now(timezone.utc) < timedelta(minutes=75):
                    lin = await provider().lineups(r["provider_id"])
                await c.execute(
                    """INSERT INTO fixture_context(fixture_id, injuries, injuries_checked_at, lineups, lineups_checked_at)
                       VALUES (%s,%s,CASE WHEN %s THEN now() END,%s,CASE WHEN %s THEN now() END)
                       ON CONFLICT (fixture_id) DO UPDATE SET
                         injuries=COALESCE(EXCLUDED.injuries, fixture_context.injuries),
                         injuries_checked_at=COALESCE(EXCLUDED.injuries_checked_at, fixture_context.injuries_checked_at),
                         lineups=COALESCE(EXCLUDED.lineups, fixture_context.lineups),
                         lineups_checked_at=COALESCE(EXCLUDED.lineups_checked_at, fixture_context.lineups_checked_at)""",
                    (r["id"], json.dumps(inj) if inj is not None else None, inj is not None,
                     json.dumps(lin) if lin else None, lin is not None))
                st["items"] += 1


async def _league_history(c, lid: int) -> list[MatchResult]:
    rows = await (await c.execute(
        """SELECT f.kickoff_utc, th.name AS home, ta.name AS away, f.ft_home, f.ft_away, m.home_xg, m.away_xg
           FROM fixtures f JOIN teams th ON th.id=f.home_team_id JOIN teams ta ON ta.id=f.away_team_id
           LEFT JOIN match_statistics m ON m.fixture_id=f.id
           WHERE f.league_id=%s AND f.status IN ('FT','AET','PEN') AND f.ft_home IS NOT NULL
           ORDER BY f.kickoff_utc""", (lid,))).fetchall()
    return [MatchResult(r["kickoff_utc"], r["home"], r["away"], r["ft_home"], r["ft_away"], r["home_xg"], r["away_xg"])
            for r in rows]


def _material_change(old: dict | None, new: dict) -> bool:
    if old is None:
        return True
    keys = ("p_home", "p_draw", "p_away", "p_btts_yes")
    if any(abs(old[k] - new[k]) >= 0.01 for k in keys):
        return True
    return old["payload"]["context"]["lineups_status"] != new["payload"]["context"]["lineups_status"] or \
        old["payload"]["context"]["injuries_status"] != new["payload"]["context"]["injuries_status"]


async def job_predict():
    async with job_log("predict") as st:
        pool = await get_pool()
        now = datetime.now(timezone.utc)
        async with pool.connection() as c:
            ids = await _league_ids(c)
            for l in LEAGUES:
                lid = ids[l.provider_id]
                hist = await _league_history(c, lid)
                xg_share = sum(1 for m in hist if m.home_xg is not None) / max(len(hist), 1)
                cfg = FitConfig(xg_weight=0.4 if xg_share > 0.6 else 0.0)
                try:
                    model = fit(hist, as_of=now, config=cfg)
                except InsufficientDataError as e:
                    st["details"][l.slug] = f"skipped: {e}"  # never predict from too little real data
                    continue
                mv = await (await c.execute(
                    "INSERT INTO model_versions(version, league_id, fitted_at, n_matches, params) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                    (MODEL_VERSION, lid, model.fitted_at, model.n_matches, json.dumps(model.to_dict())))).fetchone()
                upcoming = await (await c.execute(
                    """SELECT f.id, f.kickoff_utc, f.season_year, f.home_team_id, f.away_team_id, th.name home, ta.name away,
                              fc.injuries, fc.injuries_checked_at, fc.lineups, fc.lineups_checked_at, f.updated_at
                       FROM fixtures f JOIN teams th ON th.id=f.home_team_id JOIN teams ta ON ta.id=f.away_team_id
                       LEFT JOIN fixture_context fc ON fc.fixture_id=f.id
                       WHERE f.league_id=%s AND f.status IN ('NS','TBD') AND f.kickoff_utc > now() + interval '2 minutes'
                         AND f.kickoff_utc < now() + interval '8 days'""", (lid,))).fetchall()
                standings = {r["team_id"]: r for r in await (await c.execute(
                    "SELECT * FROM standings WHERE league_id=%s AND season_year=(SELECT max(season_year) FROM standings WHERE league_id=%s)",
                    (lid, lid))).fetchall()}
                written = 0
                for u in upcoming:
                    inj = u["injuries"]
                    if inj:
                        for i in inj:
                            t = await (await c.execute("SELECT name FROM teams WHERE provider_id=%s", (i["team_provider_id"],))).fetchone()
                            i["team"] = t["name"] if t else "?"
                    st_rows = {}
                    for side, tid in (("home", u["home_team_id"]), ("away", u["away_team_id"])):
                        s = standings.get(tid)
                        if s:
                            st_rows[side] = {"rank": s["rank"], "points": s["points"], "played": s["played"], "group": s["group_name"]}
                    ctx = ContextAvailability(xg=xg_share > 0.6, injuries_checked=u["injuries_checked_at"] is not None,
                                              injuries=inj, lineups_confirmed=u["lineups"] is not None,
                                              lineups=u["lineups"], standings=st_rows or None)
                    pred = predict_fixture(model, home=u["home"], away=u["away"], kickoff=u["kickoff_utc"],
                                           league_slug=l.slug, history=hist, ctx=ctx, now=now)
                    row = {"p_home": pred["markets"]["home"], "p_draw": pred["markets"]["draw"], "p_away": pred["markets"]["away"],
                           "p_btts_yes": pred["markets"]["btts_yes"], "payload": pred}
                    prev = await (await c.execute(
                        "SELECT p_home, p_draw, p_away, p_btts_yes, payload FROM predictions WHERE fixture_id=%s ORDER BY created_at DESC LIMIT 1",
                        (u["id"],))).fetchone()
                    if not _material_change(prev, row):
                        continue
                    payload = json.dumps(pred, default=str, sort_keys=True)
                    freshness = {"fixture_updated_at": u["updated_at"], "model_fitted_at": model.fitted_at,
                                 "injuries_checked_at": u["injuries_checked_at"], "lineups_checked_at": u["lineups_checked_at"],
                                 "history_matches": model.n_matches}
                    p = await (await c.execute(
                        """INSERT INTO predictions(fixture_id, model_version_id, model_version, kickoff_utc, data_source, input_freshness,
                               p_home, p_draw, p_away, p_btts_yes, p_over, xg_home, xg_away, confidence, completeness, payload, payload_sha256)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (u["id"], mv["id"], MODEL_VERSION, u["kickoff_utc"], provider().name, json.dumps(freshness, default=str),
                         row["p_home"], row["p_draw"], row["p_away"], row["p_btts_yes"], json.dumps(pred["markets"]["over"]),
                         pred["rates"]["home"], pred["rates"]["away"], pred["confidence"], pred["completeness"]["score"],
                         payload, hashlib.sha256(payload.encode()).hexdigest()))).fetchone()
                    expl = llm_polish(build_explanation(pred), (u["home"], u["away"]))
                    await c.execute("INSERT INTO prediction_explanations(prediction_id, explanation, source) VALUES (%s,%s,%s)",
                                    (p["id"], json.dumps(expl), expl["source"]))
                    written += 1
                st["details"][l.slug] = {"fitted_on": model.n_matches, "upcoming": len(upcoming), "written": written}
                st["items"] += written


async def job_live():
    pool = await get_pool()
    async with pool.connection() as c:
        active = await (await c.execute(
            """SELECT 1 FROM fixtures WHERE status = ANY(%s)
               OR (status IN ('NS','TBD') AND kickoff_utc BETWEEN now() - interval '10 minutes' AND now() + interval '5 minutes') LIMIT 1""",
            (list(LIVE_STATUSES),))).fetchone()
    if not active:
        return  # don't spend API quota when nothing is on
    async with job_log("live") as st:
        async with pool.connection() as c:
            ids = await _league_ids(c)
            live = await provider().live_fixtures([l.provider_id for l in LEAGUES])
            live_ids = {f.provider_id for f in live}
            for f in live:
                if f.league_provider_id in ids:
                    await _upsert_fixture(c, f, ids[f.league_provider_id])
            # Matches that just left the live feed: fetch once to record the final status/score.
            stale = await (await c.execute("SELECT provider_id, league_id FROM fixtures WHERE status = ANY(%s)",
                                           (list(LIVE_STATUSES),))).fetchall()
            for r in stale:
                if r["provider_id"] not in live_ids:
                    f = await provider().fixture(r["provider_id"])
                    if f:
                        await _upsert_fixture(c, f, r["league_id"])
            st["items"] = len(live)


async def job_settle():
    async with job_log("settle") as st:
        pool = await get_pool()
        async with pool.connection() as c:
            # Official pre-match prediction = latest one created before kickoff.
            rows = await (await c.execute(
                """SELECT DISTINCT ON (p.fixture_id) p.id, p.payload, f.status, f.ft_home, f.ft_away, f.id AS fixture_id
                   FROM predictions p JOIN fixtures f ON f.id=p.fixture_id
                   WHERE (f.status = ANY(%s) OR f.status = ANY(%s)) AND p.created_at < f.kickoff_utc
                     AND NOT EXISTS (SELECT 1 FROM prediction_settlements s WHERE s.prediction_id IN
                                     (SELECT id FROM predictions WHERE fixture_id=f.id))
                   ORDER BY p.fixture_id, p.created_at DESC""", (list(FINAL_STATUSES), list(VOID_STATUSES)))).fetchall()
            for r in rows:
                score = FinalScore(r["status"], r["ft_home"], r["ft_away"])
                odds = {}
                if settings.odds_enabled:
                    for o in await (await c.execute(
                            "SELECT DISTINCT ON (market) market, selections FROM odds_snapshots WHERE fixture_id=%s ORDER BY market, fetched_at DESC",
                            (r["fixture_id"],))).fetchall():
                        odds[o["market"]] = o["selections"]
                for pk in r["payload"]["picks"]:
                    out = settle_pick(pk["market"], pk["selection"], score)
                    if out == Outcome.PENDING:
                        continue
                    y = 1.0 if out == Outcome.WON else 0.0
                    brier = None if out == Outcome.VOID else (pk["p"] - y) ** 2
                    ll = None if out == Outcome.VOID else -math.log(max(pk["p"] if y else 1 - pk["p"], 1e-12))
                    dec = (odds.get(pk["market"]) or {}).get(pk["selection"])
                    await c.execute(
                        """INSERT INTO prediction_settlements(prediction_id, market, selection, probability, outcome, brier, log_loss,
                                                              decimal_odds, final_home, final_away)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                        (r["id"], pk["market"], pk["selection"], pk["p"], out.value, brier, ll, dec, r["ft_home"], r["ft_away"]))
                    st["items"] += 1


async def job_odds():
    if not settings.odds_enabled:
        return
    async with job_log("odds") as st:
        pool = await get_pool()
        async with pool.connection() as c:
            rows = await (await c.execute(
                "SELECT id, provider_id FROM fixtures WHERE status='NS' AND kickoff_utc BETWEEN now() AND now() + interval '36 hours'")).fetchall()
            for r in rows:
                for o in await provider().odds(r["provider_id"]):
                    await c.execute("INSERT INTO odds_snapshots(fixture_id, bookmaker, market, selections, fetched_at) VALUES (%s,%s,%s,%s,%s)",
                                    (r["id"], o.bookmaker, o.market, json.dumps(o.selections), o.fetched_at))
                    st["items"] += 1


JOBS = {"coverage": job_coverage, "fixtures": job_fixtures, "history": job_history, "context": job_context,
        "predict": job_predict, "live": job_live, "settle": job_settle, "odds": job_odds}


async def daily_pipeline():
    """Full refresh in dependency order (also what the admin 'Refresh all' button runs)."""
    for name in ("coverage", "fixtures", "history", "context", "predict", "settle"):
        await JOBS[name]()
