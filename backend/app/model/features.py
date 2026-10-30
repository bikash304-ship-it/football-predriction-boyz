"""Descriptive team statistics computed from verified results only.

These numbers feed (a) small, bounded rate adjustments and (b) the explanation text.
They never replace the fitted model; they are context.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Sequence

from .dixon_coles import MatchResult


@dataclass
class SplitStats:
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: float
    goals_against: float
    gf_per_match: float | None
    ga_per_match: float | None
    btts_rate: float | None
    over15_rate: float | None
    over25_rate: float | None
    over35_rate: float | None
    clean_sheet_rate: float | None
    failed_to_score_rate: float | None
    xg_for_per_match: float | None
    xg_against_per_match: float | None
    form: str  # most recent first, e.g. "WWDLW"


@dataclass
class TeamProfile:
    team: str
    last5: SplitStats
    last10: SplitStats
    home: SplitStats   # last 10 home matches
    away: SplitStats   # last 10 away matches
    rest_days: float | None
    matches_last_14_days: int
    last_match_was_away: bool | None

    def to_dict(self) -> dict:
        return asdict(self)


def _split(team: str, ms: Sequence[MatchResult]) -> SplitStats:
    n = len(ms)
    w = d = l = 0
    gf = ga = 0.0
    btts = o15 = o25 = o35 = cs = fts = 0
    xgf = xga = 0.0
    xg_n = 0
    form = []
    for m in ms:
        is_home = m.home == team
        f, a = (m.home_goals, m.away_goals) if is_home else (m.away_goals, m.home_goals)
        gf += f
        ga += a
        if f > a:
            w += 1; form.append("W")
        elif f == a:
            d += 1; form.append("D")
        else:
            l += 1; form.append("L")
        btts += f > 0 and a > 0
        t = f + a
        o15 += t > 1.5; o25 += t > 2.5; o35 += t > 3.5
        cs += a == 0; fts += f == 0
        if m.home_xg is not None and m.away_xg is not None:
            xgf += m.home_xg if is_home else m.away_xg
            xga += m.away_xg if is_home else m.home_xg
            xg_n += 1
    r = (lambda x: x / n) if n else (lambda x: None)
    return SplitStats(
        played=n, wins=w, draws=d, losses=l, goals_for=gf, goals_against=ga,
        gf_per_match=r(gf), ga_per_match=r(ga), btts_rate=r(btts),
        over15_rate=r(o15), over25_rate=r(o25), over35_rate=r(o35),
        clean_sheet_rate=r(cs), failed_to_score_rate=r(fts),
        xg_for_per_match=(xgf / xg_n) if xg_n else None,
        xg_against_per_match=(xga / xg_n) if xg_n else None,
        form="".join(form),
    )


def team_profile(team: str, history: Sequence[MatchResult], as_of: datetime) -> TeamProfile:
    past = sorted((m for m in history if m.date < as_of and team in (m.home, m.away)),
                  key=lambda m: m.date, reverse=True)
    home = [m for m in past if m.home == team][:10]
    away = [m for m in past if m.away == team][:10]
    rest = (as_of - past[0].date).total_seconds() / 86400 if past else None
    last14 = sum(1 for m in past if (as_of - m.date).days <= 14)
    return TeamProfile(
        team=team, last5=_split(team, past[:5]), last10=_split(team, past[:10]),
        home=_split(team, home), away=_split(team, away),
        rest_days=rest, matches_last_14_days=last14,
        last_match_was_away=(past[0].away == team) if past else None,
    )


def head_to_head(home: str, away: str, history: Sequence[MatchResult], as_of: datetime, limit: int = 6) -> list[dict]:
    rows = sorted((m for m in history if m.date < as_of and {m.home, m.away} == {home, away}),
                  key=lambda m: m.date, reverse=True)[:limit]
    return [{"date": m.date.isoformat(), "home": m.home, "away": m.away,
             "home_goals": m.home_goals, "away_goals": m.away_goals} for m in rows]


# ----------------------------------------------------------------- bounded adjustments
@dataclass
class Adjustment:
    side: str          # "home" | "away"
    factor: float      # multiplier on that side's expected goals
    reason: str


def rate_adjustments(home: TeamProfile, away: TeamProfile, league_slug: str) -> list[Adjustment]:
    """Small, transparent, capped adjustments for factors the base fit cannot see.

    Kept deliberately conservative (max +/-5% each): the literature finds these effects
    real but small, and over-adjusting hurts calibration more than ignoring them.
    """
    adj: list[Adjustment] = []
    for side, p in (("home", home), ("away", away)):
        if p.rest_days is not None and p.rest_days < 3.0:
            adj.append(Adjustment(side, 0.96, f"{p.team} on short rest ({p.rest_days:.1f} days since last match)"))
        if p.matches_last_14_days >= 5:
            adj.append(Adjustment(side, 0.97, f"{p.team} congested schedule ({p.matches_last_14_days} matches in 14 days)"))
    if league_slug == "mls" and away.last_match_was_away and away.rest_days is not None and away.rest_days < 5:
        adj.append(Adjustment("away", 0.97, f"{away.team} on a consecutive road trip with <5 days rest (MLS travel)"))
    return adj


def apply_adjustments(adj: list[Adjustment]) -> tuple[float, float]:
    h = a = 1.0
    for x in adj:
        if x.side == "home":
            h *= x.factor
        else:
            a *= x.factor
    # Global cap so stacked adjustments never move a rate by more than 10%.
    clamp = lambda v: min(max(v, 0.90), 1.10)
    return clamp(h), clamp(a)
