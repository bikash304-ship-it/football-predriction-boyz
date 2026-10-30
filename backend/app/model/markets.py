"""Derive every betting market from a single score-probability matrix.

Because 1X2, BTTS and Over/Under all come from the same matrix, they are mutually
consistent by construction (e.g. P(Over 0.5) == 1 - P(0-0) == 1 - P(BTTS No and Under 0.5 ...)).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

OU_LINES = (0.5, 1.5, 2.5, 3.5, 4.5)


@dataclass(frozen=True)
class MarketProbabilities:
    home: float
    draw: float
    away: float
    btts_yes: float
    btts_no: float
    over: dict[str, float]     # keyed "0.5", "1.5", ...
    under: dict[str, float]
    expected_home_goals: float
    expected_away_goals: float
    top_scores: list[dict]     # [{"score": "1-0", "home": 1, "away": 0, "p": 0.12}, ...]
    total_goals_dist: list[float]  # P(total == k) for k = 0..N

    def to_dict(self) -> dict:
        return asdict(self)


def derive_markets(matrix: np.ndarray, top_n: int = 3) -> MarketProbabilities:
    m = np.asarray(matrix, dtype=float)
    if m.ndim != 2 or m.shape[0] != m.shape[1]:
        raise ValueError("score matrix must be square")
    total = m.sum()
    if not np.isclose(total, 1.0, atol=1e-9):
        m = m / total

    home = float(np.tril(m, -1).sum())
    draw = float(np.trace(m))
    away = float(np.triu(m, 1).sum())

    btts_no = float(m[0, :].sum() + m[:, 0].sum() - m[0, 0])
    btts_yes = 1.0 - btts_no

    n = m.shape[0]
    goals = np.add.outer(np.arange(n), np.arange(n))
    total_dist = np.bincount(goals.ravel(), weights=m.ravel(), minlength=2 * n - 1).tolist()
    cum = np.cumsum(total_dist)
    over, under = {}, {}
    for line in OU_LINES:
        u = float(cum[int(line)])  # P(total <= floor(line))
        under[str(line)] = u
        over[str(line)] = 1.0 - u

    eh = float((m.sum(axis=1) * np.arange(n)).sum())
    ea = float((m.sum(axis=0) * np.arange(n)).sum())

    flat = np.argsort(m, axis=None)[::-1][:top_n]
    tops = []
    for f in flat:
        h, a = divmod(int(f), n)
        tops.append({"score": f"{h}-{a}", "home": h, "away": a, "p": float(m[h, a])})

    return MarketProbabilities(
        home=home, draw=draw, away=away,
        btts_yes=btts_yes, btts_no=btts_no,
        over=over, under=under,
        expected_home_goals=eh, expected_away_goals=ea,
        top_scores=tops, total_goals_dist=total_dist,
    )


def to_percentages(values: dict[str, float]) -> dict[str, int]:
    """Round probabilities to integer percentages that still sum to exactly 100
    (largest-remainder method) so the UI never shows 33/33/33 = 99."""
    raw = {k: v * 100 for k, v in values.items()}
    floors = {k: int(np.floor(v)) for k, v in raw.items()}
    short = 100 - sum(floors.values())
    for k in sorted(raw, key=lambda k: raw[k] - floors[k], reverse=True)[:short]:
        floors[k] += 1
    return floors


def picks(mp: MarketProbabilities) -> list[dict]:
    """The most probable outcome in each market (a pick is NOT a recommendation to bet)."""
    out = []
    one_x_two = {"1": mp.home, "X": mp.draw, "2": mp.away}
    k = max(one_x_two, key=one_x_two.get)
    out.append({"market": "1X2", "selection": k, "p": one_x_two[k]})
    out.append({"market": "BTTS", "selection": "Yes" if mp.btts_yes >= mp.btts_no else "No",
                "p": max(mp.btts_yes, mp.btts_no)})
    for line in OU_LINES:
        o, u = mp.over[str(line)], mp.under[str(line)]
        out.append({"market": f"OU{line}", "selection": "Over" if o >= u else "Under", "p": max(o, u)})
    return out


# --------------------------------------------------------------------- odds helpers
def implied_probabilities(decimal_odds: dict[str, float], method: str = "proportional") -> dict[str, float]:
    """Bookmaker odds -> margin-free implied probabilities.

    proportional: divide by the overround.
    shin-lite ("power"): find k such that sum(p_i ** k) == 1, which shades favourite-longshot bias.
    """
    raw = {k: 1.0 / v for k, v in decimal_odds.items() if v and v > 1.0}
    if len(raw) != len(decimal_odds):
        raise ValueError("all odds must be decimal and > 1.0")
    if method == "proportional":
        s = sum(raw.values())
        return {k: v / s for k, v in raw.items()}
    if method == "power":
        lo, hi = 1.0, 3.0
        vals = np.array(list(raw.values()))
        for _ in range(100):
            mid = (lo + hi) / 2
            if np.sum(vals**mid) > 1:
                lo = mid
            else:
                hi = mid
        p = vals ** ((lo + hi) / 2)
        p = p / p.sum()
        return dict(zip(raw.keys(), map(float, p)))
    raise ValueError(f"unknown method {method}")


def bookmaker_margin(decimal_odds: dict[str, float]) -> float:
    return sum(1.0 / v for v in decimal_odds.values()) - 1.0


def expected_value(model_p: float, decimal_odds: float) -> float:
    """EV per 1 unit staked. Only meaningful when the model is calibrated."""
    return model_p * decimal_odds - 1.0
