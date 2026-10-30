"""DEMO MODE — used only when API_FOOTBALL_KEY / DATABASE_URL are not configured.

Clubs are FICTIONAL and results are SIMULATED. The probabilities, however, are produced
by the real Dixon-Coles engine, fitted only on data before each kickoff, and past demo
fixtures are settled exactly like live ones — so every page and chart works end to end.
Every response carries `"demo": true` and the UI labels every demo element.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

import numpy as np

from ..leagues import LEAGUES, BY_SLUG
from ..model.dixon_coles import FitConfig, MatchResult, fit
from ..model.explain import build_explanation
from ..model.predictor import ContextAvailability, predict_fixture
from ..model.ranking import calibration_errors, summarize_settled, top_predictions
from ..model.settlement import FinalScore, settle_all
from .serialize import FINAL_STATUSES, LIVE_STATUSES, fixture_out

DEMO_CLUBS = {
    "premier-league": ["Northgate Rovers", "Kingsmere Athletic", "Hollowbrook FC", "Ravenshaw United", "Saltmarsh Town",
                       "Elmstead City", "Brackwater Albion", "Coldharbour FC", "Ferncliffe Wanderers", "Oakhurst Villa",
                       "Thornbury Rangers", "Westwick Borough"],
    "la-liga": ["Atlético Solmar", "Real Costaverde", "CD Montealto", "Deportivo Arenal", "UD Pinoblanco", "SD Río Claro",
                "CF Torreluz", "Racing Valdeoro", "Unión Sierranegra", "CD Puertolago", "Real Cantavieja", "SD Almendral"],
    "bundesliga": ["FC Grünwalden", "SV Steinbach 04", "Borussia Lindenfeld", "VfB Eichenau", "TSV Bergheide",
                   "1. FC Rotenmoor", "SC Falkenried", "Eintracht Weißensee", "FSV Kronach-Tal", "SpVgg Ahornberg",
                   "VfL Mühlenhof", "Union Silberau"],
    "ligue-1": ["AS Valmont", "Olympique Rivebelle", "FC Montclair", "Stade Lacombe", "RC Bois-Joli", "SC Beaurivage",
                "US Pierrefonte", "AJ Clairvaux", "FC Mirabelle", "Stade Hautemer", "OGC Vallon", "AC Sainte-Lune"],
    "eliteserien": ["Fjordvik IL", "Nordstrand FK", "Bjørkely SK", "Havnås BK", "Lysheim IF", "Granmo FK",
                    "Skogvang IL", "Elvebakk SK", "Tindefjell FK", "Solbakken IF", "Isfjord BK", "Mosvik IL"],
    "mls": ["Cascade City FC", "Desert Mesa SC", "Lakeshore United", "Harbor Point FC", "Prairie Wind SC", "Ridgeview FC",
            "Bayline Athletic", "Summit Peak FC", "Riverbend United", "Coastal Crown SC", "Ironworks FC", "Maple Falls SC"],
}

TZ = ZoneInfo("Europe/Oslo")
KICKOFFS = {"premier-league": [(13, 30), (16, 0), (18, 30)], "la-liga": [(14, 0), (18, 30), (21, 0)],
            "bundesliga": [(15, 30), (18, 30), (20, 30)], "ligue-1": [(15, 0), (17, 0), (20, 45)],
            "eliteserien": [(15, 0), (17, 0), (19, 15)], "mls": [(1, 30), (2, 30), (4, 30)]}


def _seed(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def _logo(name: str) -> str:
    """Initials for a placeholder crest; the frontend draws it. Real crests come from the provider."""
    return "".join(w[0] for w in name.replace(".", "").split() if w[0].isalpha())[:3].upper()


class DemoRepository:
    demo = True

    def __init__(self, today: date | None = None):
        self.today = today or datetime.now(TZ).date()
        self._build()

    # ------------------------------------------------------------------ generation
    def _build(self):
        self.fixtures: dict[int, dict] = {}
        self.preds: dict[int, dict] = {}
        self.expls: dict[int, dict] = {}
        self.history: dict[str, list[MatchResult]] = {}
        self.settled: list[dict] = []
        self.teams: dict[int, dict] = {}
        now = datetime.now(timezone.utc)
        fid = 900000
        for lg in LEAGUES:
            rng = np.random.default_rng(_seed("demo", lg.slug))
            clubs = DEMO_CLUBS[lg.slug]
            att = dict(zip(clubs, rng.normal(0, 0.22, len(clubs))))
            dfc = dict(zip(clubs, rng.normal(0, 0.18, len(clubs))))
            home_adv = 0.22 if lg.slug != "mls" else 0.30
            base = 0.12 if lg.slug in ("bundesliga", "eliteserien", "mls") else 0.05
            tids = {c: 800000 + _seed(lg.slug, c) % 99999 for c in clubs}
            for c in clubs:
                self.teams[tids[c]] = {"id": tids[c], "name": c, "logo": None, "initials": _logo(c), "league_slug": lg.slug}

            def sim(h, a, r):
                lam = np.exp(base + att[h] + dfc[a] + home_adv)
                mu = np.exp(base + att[a] + dfc[h])
                return int(r.poisson(lam)), int(r.poisson(mu))

            # ~2 seasons of history ending 15 days ago (one match per pair per "season", every 3.5 days a round)
            hist: list[MatchResult] = []
            start = datetime.combine(self.today - timedelta(days=15 + 2 * 22 * 7), time(15), tzinfo=timezone.utc)
            pairs = [(h, a) for h in clubs for a in clubs if h != a]
            for season in range(2):
                order = rng.permutation(len(pairs))
                for k, i in enumerate(order):
                    h, a = pairs[i]
                    d = start + timedelta(days=season * 154 + (k // 6) * (154 / 22), hours=float(rng.integers(0, 6)))
                    g = sim(h, a, rng)
                    hist.append(MatchResult(d, h, a, *g))
            hist.sort(key=lambda m: m.date)

            # Window fixtures: rounds every ~3-4 days from today-14 to today+7.
            round_days = [-14, -10, -7, -3, 0, 1, 4, 7]
            if lg.slug in ("premier-league", "la-liga", "bundesliga", "ligue-1"):
                round_days = [-14, -7, -3, 0, 1, 4, 7]
            rng_fx = np.random.default_rng(_seed("fx", lg.slug, self.today))
            for rn, off in enumerate(round_days):
                day = self.today + timedelta(days=off)
                perm = list(rng_fx.permutation(clubs))
                for j in range(0, len(perm), 2):
                    h, a = perm[j], perm[j + 1]
                    hh, mm = KICKOFFS[lg.slug][(j // 2) % 3]
                    local = datetime.combine(day + (timedelta(days=1) if lg.slug == "mls" else timedelta()), time(hh, mm), tzinfo=TZ)
                    ko = local.astimezone(timezone.utc)
                    fid += 1
                    mins = (now - ko).total_seconds() / 60
                    r = np.random.default_rng(_seed("res", fid, self.today))
                    status, elapsed, goals, ft = "NS", None, (None, None), (None, None)
                    if mins >= 115:
                        g = sim(h, a, r)
                        status, goals, ft = "FT", g, g
                    elif mins >= 0:
                        g = sim(h, a, r)
                        frac = min(mins / 95, 1)
                        goals = (int(round(g[0] * frac)), int(round(g[1] * frac)))
                        elapsed = int(min(mins if mins < 47 else mins - 15, 90))
                        status = "1H" if mins < 47 else ("HT" if mins < 62 else "2H")
                    if (rn == 3 and j == 0 and lg.slug in ("ligue-1", "eliteserien")) and status == "NS":
                        status = "PST"  # demonstrate postponed handling
                    self.fixtures[fid] = dict(id=fid, league=lg, kickoff_utc=ko, status=status, elapsed=elapsed,
                                              home=h, away=a, home_id=tids[h], away_id=tids[a], goals=goals, ft=ft,
                                              venue=f"{h.split()[0]} Stadium", city=h.split()[0], round=f"Round {rn + 20}")
            self.history[lg.slug] = hist

        self._predict_and_settle()

    def _predict_and_settle(self):
        by_league_day: dict[tuple[str, date], list[int]] = {}
        for fid, f in self.fixtures.items():
            by_league_day.setdefault((f["league"].slug, f["kickoff_utc"].date()), []).append(fid)
        for (slug, day), fids in sorted(by_league_day.items(), key=lambda x: x[0][1]):
            # History available before this day = generated history + window fixtures already finished.
            cutoff = datetime.combine(day, time(0), tzinfo=timezone.utc)
            hist = list(self.history[slug]) + [
                MatchResult(f["kickoff_utc"], f["home"], f["away"], *f["ft"])
                for f in self.fixtures.values()
                if f["league"].slug == slug and f["status"] == "FT" and f["kickoff_utc"] < cutoff
            ]
            model = fit(hist, as_of=cutoff, config=FitConfig())
            for fid in fids:
                f = self.fixtures[fid]
                if f["status"] in ("PST", "CANC"):
                    continue
                created = min(f["kickoff_utc"] - timedelta(hours=6), datetime.now(timezone.utc))
                ctx = ContextAvailability(xg=False, injuries_checked=False, lineups_confirmed=False,
                                          standings=None)
                pred = predict_fixture(model, home=f["home"], away=f["away"], kickoff=f["kickoff_utc"],
                                       league_slug=slug, history=hist, ctx=ctx, now=created)
                pred["demo"] = True
                self.preds[fid] = pred
                self.expls[fid] = build_explanation(pred)
                if f["status"] in FINAL_STATUSES:
                    for s in settle_all(pred["picks"], FinalScore("FT", *f["ft"])):
                        self.settled.append({**s, "probability": s["p"], "league_slug": slug, "fixture_id": fid,
                                             "settled_at": f["kickoff_utc"] + timedelta(hours=2), "decimal_odds": None,
                                             "home": f["home"], "away": f["away"], "final": f["ft"],
                                             "kickoff_utc": f["kickoff_utc"]})

    # ------------------------------------------------------------------ helpers
    def _team(self, name: str, tid: int) -> dict:
        return {"id": tid, "name": name, "logo": None, "initials": _logo(name)}

    def _out(self, f: dict) -> dict:
        return fixture_out(id=f["id"], league=f["league"], kickoff_utc=f["kickoff_utc"], status=f["status"],
                           status_long={"NS": "Not Started", "FT": "Match Finished", "PST": "Match Postponed",
                                        "1H": "First Half", "HT": "Halftime", "2H": "Second Half"}[f["status"]],
                           elapsed=f["elapsed"], home=self._team(f["home"], f["home_id"]),
                           away=self._team(f["away"], f["away_id"]), venue=f["venue"], city=f["city"],
                           round=f["round"], goals=f["goals"], ft=f["ft"], demo=True,
                           prediction=self.preds.get(f["id"]))

    def _standings(self, slug: str) -> list[dict]:
        tbl: dict[str, dict] = {}
        season_start = self.history[slug][len(self.history[slug]) // 2].date
        rows = [m for m in self.history[slug] if m.date >= season_start] + [
            MatchResult(f["kickoff_utc"], f["home"], f["away"], *f["ft"]) for f in self.fixtures.values()
            if f["league"].slug == slug and f["status"] == "FT"]
        for m in rows:
            for t, gf, ga in ((m.home, m.home_goals, m.away_goals), (m.away, m.away_goals, m.home_goals)):
                r = tbl.setdefault(t, {"team": t, "played": 0, "won": 0, "drawn": 0, "lost": 0, "goals_for": 0,
                                       "goals_against": 0, "points": 0, "form": ""})
                r["played"] += 1; r["goals_for"] += gf; r["goals_against"] += ga
                res = "W" if gf > ga else ("D" if gf == ga else "L")
                r["won" if res == "W" else "drawn" if res == "D" else "lost"] += 1
                r["points"] += {"W": 3, "D": 1, "L": 0}[res]
                r["form"] = (res + r["form"])[:5]
        out = sorted(tbl.values(), key=lambda r: (-r["points"], -(r["goals_for"] - r["goals_against"]), -r["goals_for"]))
        for i, r in enumerate(out, 1):
            r["rank"] = i
            r["initials"] = _logo(r["team"])
        return out

    # ------------------------------------------------------------------ public API
    def health(self) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        return {"demo": True, "provider": "demo (simulated)", "live_data_configured": False,
                "last_sync": {"fixtures": now, "live": now, "predictions": now, "settlement": now}, "warnings": [
                    "Demo mode: API_FOOTBALL_KEY and DATABASE_URL are not set. Clubs and results are fictional."]}

    def leagues(self) -> list[dict]:
        today_counts = {lg.slug: 0 for lg in LEAGUES}
        for f in self.fixtures.values():
            if f["kickoff_utc"].astimezone(TZ).date() == self.today:
                today_counts[f["league"].slug] += 1
        return [{"slug": l.slug, "name": l.name, "country": l.country, "country_code": l.country_code,
                 "logo": None, "today": today_counts[l.slug], "demo": True} for l in LEAGUES]

    def league(self, slug: str) -> dict | None:
        lg = BY_SLUG.get(slug)
        if not lg:
            return None
        fx = sorted((f for f in self.fixtures.values() if f["league"].slug == slug), key=lambda f: f["kickoff_utc"])
        return {"league": next(l for l in self.leagues() if l["slug"] == slug), "standings": self._standings(slug),
                "fixtures": [self._out(f) for f in fx], "demo": True}

    def fixtures_on(self, day: date, tz: str = "Europe/Oslo", league: str | None = None) -> list[dict]:
        z = ZoneInfo(tz)
        fx = [f for f in self.fixtures.values() if f["kickoff_utc"].astimezone(z).date() == day
              and (not league or f["league"].slug == league)]
        return [self._out(f) for f in sorted(fx, key=lambda f: f["kickoff_utc"])]

    def fixtures_range(self, start: date, days: int, tz: str = "Europe/Oslo") -> list[dict]:
        z = ZoneInfo(tz)
        end = start + timedelta(days=days)
        fx = [f for f in self.fixtures.values() if start <= f["kickoff_utc"].astimezone(z).date() < end]
        return [self._out(f) for f in sorted(fx, key=lambda f: f["kickoff_utc"])]

    def live(self) -> list[dict]:
        return [self._out(f) for f in self.fixtures.values() if f["status"] in LIVE_STATUSES]

    def fixture_detail(self, fid: int) -> dict | None:
        f = self.fixtures.get(fid)
        if not f:
            return None
        pred = self.preds.get(fid)
        settled = [s for s in self.settled if s["fixture_id"] == fid]
        standings = self._standings(f["league"].slug)
        return {"fixture": self._out(f), "prediction": pred, "explanation": self.expls.get(fid),
                "standings": standings, "settlement": settled or None,
                "prediction_history": [{"created_at": pred["created_at"], **pred["display"]["1x2"]}] if pred else [],
                "freshness": {"fixtures": datetime.now(timezone.utc).isoformat(), "model_fit": pred["model_fit"]["fitted_at"] if pred else None},
                "demo": True}

    def top(self, day: date, tz: str = "Europe/Oslo", market: str | None = None, league: str | None = None,
            min_p: float = 0.0, limit: int = 20) -> list[dict]:
        items = [{"fixture": fx, "prediction": self.preds[fx["id"]]}
                 for fx in self.fixtures_on(day, tz, league) if fx["id"] in self.preds and fx["status"] == "NS"]
        calib = calibration_errors(self.settled, min_n=30)
        return top_predictions(items, market=market, min_p=min_p, calib=calib, limit=limit)

    def analytics(self) -> dict:
        s = summarize_settled(self.settled, datetime.now(timezone.utc))
        s["demo"] = True
        s["note"] = "Demo analytics: computed honestly from simulated results of fictional clubs."
        return s

    def history_rows(self, league: str | None = None, market: str | None = None, limit: int = 300) -> list[dict]:
        rows = [r for r in self.settled if (not league or r["league_slug"] == league) and (not market or r["market"] == market)]
        rows.sort(key=lambda r: r["settled_at"], reverse=True)
        return [{**{k: v for k, v in r.items() if k not in ("settled_at", "kickoff_utc")},
                 "settled_at": r["settled_at"].isoformat(), "kickoff_utc": r["kickoff_utc"].isoformat(), "demo": True}
                for r in rows[:limit]]

    def search(self, q: str) -> dict:
        ql = q.lower().strip()
        teams = [t for t in self.teams.values() if ql in t["name"].lower()][:10]
        ids = {t["id"] for t in teams}
        matches = [self._out(f) for f in sorted(self.fixtures.values(), key=lambda f: f["kickoff_utc"])
                   if f["home_id"] in ids or f["away_id"] in ids][:20]
        return {"teams": teams, "fixtures": matches, "demo": True}


@lru_cache(maxsize=2)
def get_demo_repo(day: date) -> DemoRepository:
    return DemoRepository(day)
