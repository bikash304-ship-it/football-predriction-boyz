"""Dixon-Coles goal model with time-decay weighting, shrinkage and optional xG blending.

Model (per league):
    log(lambda_home) = attack[home] + defence[away] + home_adv
    log(mu_away)     = attack[away] + defence[home]
    P(x, y) = tau(x, y; lambda, mu, rho) * Pois(x; lambda) * Pois(y; mu)

Identifiability: sum(attack) == 0 (the last attack parameter is implied).
Small-sample protection: L2 penalty pulls attack/defence toward the league mean (0),
so a promoted side with five matches is not rated as a world-beater.
Recency: each match is weighted by exp(-xi * days_since_match).

Everything downstream (1X2, BTTS, Over/Under, correct scores) is derived from ONE
score matrix produced by this model, so markets can never contradict each other.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Sequence

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

MAX_GOALS = 10  # score matrix is (MAX_GOALS+1) x (MAX_GOALS+1); mass beyond is < 1e-6 for realistic rates


@dataclass(frozen=True)
class MatchResult:
    """A completed match used for fitting. Dates must be timezone-aware."""

    date: datetime
    home: str
    away: str
    home_goals: int
    away_goals: int
    home_xg: float | None = None
    away_xg: float | None = None


@dataclass
class FitConfig:
    xi: float = 0.0019          # time-decay per day (half-life ~ 365 days); tuned by backtest
    shrinkage: float = 0.08     # L2 strength on attack/defence; tuned by backtest
    xg_weight: float = 0.0      # 0 = goals only, 0.5 = equal blend of goals and xG (when xG present)
    min_matches: int = 30       # refuse to fit a league with less history than this


@dataclass
class DixonColesModel:
    teams: list[str]
    attack: dict[str, float]
    defence: dict[str, float]
    home_adv: float
    rho: float
    fitted_at: datetime
    n_matches: int
    matches_per_team: dict[str, int] = field(default_factory=dict)
    config: FitConfig = field(default_factory=FitConfig)

    # ------------------------------------------------------------------ rates
    def expected_goals(self, home: str, away: str) -> tuple[float, float]:
        """Expected goals for an unknown team default to league-average strength (0)."""
        ah, dh = self.attack.get(home, 0.0), self.defence.get(home, 0.0)
        aa, da = self.attack.get(away, 0.0), self.defence.get(away, 0.0)
        lam = float(np.exp(ah + da + self.home_adv))
        mu = float(np.exp(aa + dh))
        return lam, mu

    def score_matrix(self, home: str, away: str, lam_mult: float = 1.0, mu_mult: float = 1.0) -> np.ndarray:
        lam, mu = self.expected_goals(home, away)
        return score_matrix(lam * lam_mult, mu * mu_mult, self.rho)

    def to_dict(self) -> dict:
        return {
            "teams": self.teams,
            "attack": self.attack,
            "defence": self.defence,
            "home_adv": self.home_adv,
            "rho": self.rho,
            "fitted_at": self.fitted_at.isoformat(),
            "n_matches": self.n_matches,
            "matches_per_team": self.matches_per_team,
            "config": self.config.__dict__,
        }


# ---------------------------------------------------------------------- core maths
def tau(x: np.ndarray, y: np.ndarray, lam: np.ndarray, mu: np.ndarray, rho: float) -> np.ndarray:
    """Dixon-Coles low-score dependence correction."""
    t = np.ones_like(lam, dtype=float)
    m00 = (x == 0) & (y == 0)
    m01 = (x == 0) & (y == 1)
    m10 = (x == 1) & (y == 0)
    m11 = (x == 1) & (y == 1)
    t = np.where(m00, 1.0 - lam * mu * rho, t)
    t = np.where(m01, 1.0 + lam * rho, t)
    t = np.where(m10, 1.0 + mu * rho, t)
    t = np.where(m11, 1.0 - rho, t)
    return t


def poisson_pmf_vector(rate: float, n: int = MAX_GOALS) -> np.ndarray:
    k = np.arange(n + 1)
    return np.exp(k * np.log(rate) - rate - gammaln(k + 1))


def score_matrix(lam: float, mu: float, rho: float = 0.0, max_goals: int = MAX_GOALS) -> np.ndarray:
    """Joint probability of each full-time score. Rows = home goals, cols = away goals.

    The matrix is renormalised to sum to exactly 1 so derived markets add up to 100%.
    """
    if lam <= 0 or mu <= 0:
        raise ValueError("Goal rates must be positive")
    ph = poisson_pmf_vector(lam, max_goals)
    pa = poisson_pmf_vector(mu, max_goals)
    m = np.outer(ph, pa)
    m[0, 0] *= 1.0 - lam * mu * rho
    m[0, 1] *= 1.0 + lam * rho
    m[1, 0] *= 1.0 + mu * rho
    m[1, 1] *= 1.0 - rho
    m = np.clip(m, 0.0, None)
    return m / m.sum()


# ---------------------------------------------------------------------- fitting
def _rho_bounds(lam: np.ndarray, mu: np.ndarray) -> tuple[float, float]:
    """tau must stay positive for every observed (lam, mu)."""
    lo = max(-1.0 / np.max(lam), -1.0 / np.max(mu))
    hi = min(1.0 / np.max(lam * mu), 1.0)
    return lo + 1e-6, hi - 1e-6


def fit(matches: Sequence[MatchResult], as_of: datetime | None = None, config: FitConfig | None = None) -> DixonColesModel:
    """Fit the model on matches played strictly before `as_of` (prevents future leakage)."""
    config = config or FitConfig()
    as_of = as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")

    data = [m for m in matches if m.date < as_of]
    if len(data) < config.min_matches:
        raise InsufficientDataError(f"Need at least {config.min_matches} completed matches, got {len(data)}")

    teams = sorted({m.home for m in data} | {m.away for m in data})
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    hi = np.array([idx[m.home] for m in data])
    ai = np.array([idx[m.away] for m in data])
    hg = np.array([m.home_goals for m in data], dtype=float)
    ag = np.array([m.away_goals for m in data], dtype=float)

    # Optional xG blend: the Poisson likelihood accepts non-integer targets via gammaln.
    hy, ay = hg.copy(), ag.copy()
    if config.xg_weight > 0:
        for k, m in enumerate(data):
            if m.home_xg is not None and m.away_xg is not None:
                hy[k] = (1 - config.xg_weight) * hg[k] + config.xg_weight * m.home_xg
                ay[k] = (1 - config.xg_weight) * ag[k] + config.xg_weight * m.away_xg

    days = np.array([(as_of - m.date).total_seconds() / 86400.0 for m in data])
    w = np.exp(-config.xi * days)

    low = (hg <= 1) & (ag <= 1)  # tau only touches these cells
    hg_i, ag_i = hg.astype(int), ag.astype(int)
    const_h = gammaln(hy + 1)
    const_a = gammaln(ay + 1)

    def unpack(p: np.ndarray):
        att = np.append(p[: n - 1], -np.sum(p[: n - 1]))
        dfc = p[n - 1 : 2 * n - 1]
        return att, dfc, p[2 * n - 1], p[2 * n]

    def nll(p: np.ndarray) -> float:
        att, dfc, home, rho = unpack(p)
        log_lam = att[hi] + dfc[ai] + home
        log_mu = att[ai] + dfc[hi]
        lam, mu = np.exp(log_lam), np.exp(log_mu)
        ll = hy * log_lam - lam - const_h + ay * log_mu - mu - const_a
        t = tau(hg_i[low], ag_i[low], lam[low], mu[low], rho)
        if np.any(t <= 0):
            return 1e12
        ll_low = np.zeros_like(ll)
        ll_low[low] = np.log(t)
        penalty = config.shrinkage * (np.sum(att**2) + np.sum(dfc**2))
        return float(-np.sum(w * (ll + ll_low)) + penalty)

    x0 = np.concatenate([np.zeros(n - 1), np.zeros(n), [0.25], [-0.05]])
    bounds = [(-3, 3)] * (2 * n - 1) + [(-1, 1), (-0.25, 0.25)]
    res = minimize(nll, x0, method="L-BFGS-B", bounds=bounds, options={"maxiter": 2000})
    if not res.success and res.status not in (0, 1, 2):
        raise RuntimeError(f"Dixon-Coles fit failed: {res.message}")

    att, dfc, home, rho = unpack(res.x)
    # Keep rho inside the valid region for every fitted rate.
    lam_all = np.exp(att[hi] + dfc[ai] + home)
    mu_all = np.exp(att[ai] + dfc[hi])
    lo, hi_b = _rho_bounds(lam_all, mu_all)
    rho = float(np.clip(rho, lo, hi_b))

    counts: dict[str, int] = {t: 0 for t in teams}
    for m in data:
        counts[m.home] += 1
        counts[m.away] += 1

    return DixonColesModel(
        teams=teams,
        attack={t: float(att[idx[t]]) for t in teams},
        defence={t: float(dfc[idx[t]]) for t in teams},
        home_adv=float(home),
        rho=rho,
        fitted_at=as_of,
        n_matches=len(data),
        matches_per_team=counts,
        config=config,
    )


class InsufficientDataError(Exception):
    """Raised when there is not enough verified history to fit a league model."""


def iter_results(rows: Iterable[dict]) -> list[MatchResult]:
    """Convenience: build MatchResult objects from plain dicts (e.g. DB rows)."""
    return [
        MatchResult(
            date=r["date"], home=r["home"], away=r["away"],
            home_goals=int(r["home_goals"]), away_goals=int(r["away_goals"]),
            home_xg=r.get("home_xg"), away_xg=r.get("away_xg"),
        )
        for r in rows
    ]
