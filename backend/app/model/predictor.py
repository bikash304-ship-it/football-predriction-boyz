"""Turn a fitted league model + verified context into one immutable prediction payload."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

import numpy as np
from scipy.special import gammaln

from .dixon_coles import MAX_GOALS, DixonColesModel, MatchResult, score_matrix
from .features import apply_adjustments, head_to_head, rate_adjustments, team_profile
from .markets import derive_markets, picks, to_percentages

MODEL_VERSION = "dc-1.0.0"  # bump whenever the model, features or adjustments change


@dataclass
class ContextAvailability:
    xg: bool = False
    injuries_checked: bool = False      # provider queried AND responded
    injuries: list[dict] | None = None  # verified injuries/suspensions, as provided
    lineups_confirmed: bool = False
    lineups: dict | None = None
    standings: dict | None = None       # {"home": {...row}, "away": {...row}}


def _uncertainty_band(lam: float, mu: float, rho: float, n_eff: float, samples: int = 300, seed: int = 7) -> dict:
    """Approximate parameter uncertainty: perturb log-rates by their rough standard error
    (~1/sqrt(goals observed)) and report the 10th-90th percentile of each 1X2 outcome."""
    rng = np.random.default_rng(seed)
    se = 1.0 / np.sqrt(max(n_eff * 1.35, 1.0))
    ls = lam * np.exp(rng.normal(0, se, samples))
    ms = mu * np.exp(rng.normal(0, se, samples))
    k = np.arange(MAX_GOALS + 1)
    ph = np.exp(k[None, :] * np.log(ls[:, None]) - ls[:, None] - gammaln(k + 1)[None, :])
    pa = np.exp(k[None, :] * np.log(ms[:, None]) - ms[:, None] - gammaln(k + 1)[None, :])
    M = ph[:, :, None] * pa[:, None, :]
    M[:, 0, 0] *= 1 - ls * ms * rho
    M[:, 0, 1] *= 1 + ls * rho
    M[:, 1, 0] *= 1 + ms * rho
    M[:, 1, 1] *= 1 - rho
    M /= M.sum(axis=(1, 2), keepdims=True)
    lower = np.tril(np.ones((MAX_GOALS + 1,) * 2), -1).astype(bool)
    hs = M[:, lower].sum(axis=1)
    ds = np.trace(M, axis1=1, axis2=2)
    as_ = M[:, lower.T].sum(axis=1)
    q = lambda xs: [float(np.percentile(xs, 10)), float(np.percentile(xs, 90))]
    return {"home": q(hs), "draw": q(ds), "away": q(as_), "log_rate_se": float(se)}


def data_completeness(model: DixonColesModel, home: str, away: str, ctx: ContextAvailability) -> dict:
    nh = model.matches_per_team.get(home, 0)
    na = model.matches_per_team.get(away, 0)
    components = {
        "history_home": min(nh / 20, 1.0),
        "history_away": min(na / 20, 1.0),
        "xg": 1.0 if ctx.xg else 0.0,
        "injuries": 1.0 if ctx.injuries_checked else 0.0,
        "lineups": 1.0 if ctx.lineups_confirmed else 0.0,
    }
    weights = {"history_home": 0.35, "history_away": 0.35, "xg": 0.1, "injuries": 0.1, "lineups": 0.1}
    score = sum(components[k] * weights[k] for k in weights)
    missing = []
    if nh < 10: missing.append(f"Limited history for {home} ({nh} matches) — rating shrunk toward league average")
    if na < 10: missing.append(f"Limited history for {away} ({na} matches) — rating shrunk toward league average")
    if not ctx.xg: missing.append("xG not available for this league/plan — model uses goals only")
    if not ctx.injuries_checked: missing.append("Injury/suspension data unavailable — not reflected in probabilities")
    if not ctx.lineups_confirmed: missing.append("Starting lineups not yet confirmed")
    return {"score": round(score, 3), "components": components, "missing": missing}


def confidence_label(completeness: float, band: dict) -> str:
    width = max(band["home"][1] - band["home"][0], band["away"][1] - band["away"][0])
    if completeness >= 0.75 and width <= 0.12:
        return "High"
    if completeness >= 0.5 and width <= 0.20:
        return "Medium"
    return "Low"


def predict_fixture(
    model: DixonColesModel,
    *,
    home: str,
    away: str,
    kickoff: datetime,
    league_slug: str,
    history: Sequence[MatchResult],
    ctx: ContextAvailability | None = None,
    now: datetime | None = None,
) -> dict:
    ctx = ctx or ContextAvailability()
    now = now or datetime.now(timezone.utc)

    hp = team_profile(home, history, kickoff)
    ap = team_profile(away, history, kickoff)
    adjustments = rate_adjustments(hp, ap, league_slug)
    hm, am = apply_adjustments(adjustments)

    base_lam, base_mu = model.expected_goals(home, away)
    lam, mu = base_lam * hm, base_mu * am
    matrix = score_matrix(lam, mu, model.rho)
    mk = derive_markets(matrix)

    n_eff = min(model.matches_per_team.get(home, 0), model.matches_per_team.get(away, 0))
    band = _uncertainty_band(lam, mu, model.rho, n_eff)
    completeness = data_completeness(model, home, away, ctx)

    return {
        "model_version": MODEL_VERSION,
        "created_at": now.isoformat(),
        "kickoff": kickoff.isoformat(),
        "home": home,
        "away": away,
        "markets": mk.to_dict(),
        "display": {
            "1x2": to_percentages({"home": mk.home, "draw": mk.draw, "away": mk.away}),
            "btts": to_percentages({"yes": mk.btts_yes, "no": mk.btts_no}),
            "ou": {l: to_percentages({"over": mk.over[l], "under": mk.under[l]}) for l in mk.over},
        },
        "picks": picks(mk),
        "score_matrix": np.round(matrix[:7, :7], 5).tolist(),  # 0-6 goals each, for the heatmap
        "rates": {"base_home": base_lam, "base_away": base_mu, "home": lam, "away": mu, "rho": model.rho,
                  "home_adv": model.home_adv},
        "adjustments": [a.__dict__ for a in adjustments],
        "uncertainty": band,
        "completeness": completeness,
        "confidence": confidence_label(completeness["score"], band),
        "context": {
            "home_profile": hp.to_dict(),
            "away_profile": ap.to_dict(),
            "h2h": head_to_head(home, away, history, kickoff),
            "injuries": ctx.injuries if ctx.injuries_checked else None,
            "injuries_status": "verified" if ctx.injuries_checked else "unavailable",
            "lineups": ctx.lineups if ctx.lineups_confirmed else None,
            "lineups_status": "confirmed" if ctx.lineups_confirmed else "not confirmed",
            "standings": ctx.standings,
            "ratings": {
                "home_attack": model.attack.get(home), "home_defence": model.defence.get(home),
                "away_attack": model.attack.get(away), "away_defence": model.defence.get(away),
            },
        },
        "model_fit": {"fitted_at": model.fitted_at.isoformat(), "n_matches": model.n_matches,
                      "config": model.config.__dict__},
    }
