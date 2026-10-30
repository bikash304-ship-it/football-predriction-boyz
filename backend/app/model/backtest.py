"""Time-ordered walk-forward backtest.

For each test match, the model is fitted ONLY on matches that kicked off before that
match's date (refit every `refit_days`). This prevents future-data leakage.
Hyper-parameters (xi, shrinkage) are chosen by `tune`, which is how the model is
calibrated: calibration happens at the goal-model level so all markets stay consistent.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from itertools import product
from typing import Sequence

import numpy as np

from .calibration import (brier_binary, brier_multiclass, expected_calibration_error,
                          log_loss_binary, log_loss_multiclass, reliability_bins)
from .dixon_coles import FitConfig, InsufficientDataError, MatchResult, fit
from .markets import derive_markets
from .settlement import FinalScore, outcome_vectors


def walk_forward(matches: Sequence[MatchResult], start: datetime, config: FitConfig | None = None,
                 refit_days: int = 7) -> dict:
    config = config or FitConfig()
    ms = sorted(matches, key=lambda m: m.date)
    test = [m for m in ms if m.date >= start]
    p1x2, y1x2, pb, yb, po, yo = [], [], [], [], [], []
    model, next_refit = None, None
    skipped = 0
    for m in test:
        if model is None or m.date >= next_refit:
            # Fit on everything strictly before this match's calendar day.
            day = m.date.replace(hour=0, minute=0, second=0, microsecond=0)
            try:
                model = fit(ms, as_of=day, config=config)
            except InsufficientDataError:
                skipped += 1
                continue
            next_refit = day + timedelta(days=refit_days)
        mk = derive_markets(model.score_matrix(m.home, m.away))
        ov = outcome_vectors(FinalScore("FT", m.home_goals, m.away_goals))
        p1x2.append([mk.home, mk.draw, mk.away]); y1x2.append(ov["1X2"])
        pb.append(mk.btts_yes); yb.append(ov["BTTS"][0])
        po.append(mk.over["2.5"]); yo.append(ov["OU2.5"][0])
    if not p1x2:
        return {"n": 0, "skipped": skipped}
    P, Y = np.array(p1x2), np.array(y1x2)
    hit = float(np.mean(np.argmax(P, axis=1) == np.argmax(Y, axis=1)))
    base = Y.mean(axis=0)  # naive climatology baseline (in-sample, generous to the baseline)
    return {
        "n": len(P), "skipped": skipped, "config": config.__dict__,
        "1x2": {"brier": brier_multiclass(P, Y), "log_loss": log_loss_multiclass(P, Y), "accuracy": hit,
                "baseline_brier": brier_multiclass(np.tile(base, (len(Y), 1)), Y)},
        "btts": {"brier": brier_binary(pb, yb), "log_loss": log_loss_binary(pb, yb),
                 "ece": expected_calibration_error(pb, yb), "reliability": reliability_bins(pb, yb)},
        "ou2.5": {"brier": brier_binary(po, yo), "log_loss": log_loss_binary(po, yo),
                  "ece": expected_calibration_error(po, yo), "reliability": reliability_bins(po, yo)},
        "home_win_reliability": reliability_bins(P[:, 0], Y[:, 0]),
    }


def tune(matches: Sequence[MatchResult], start: datetime,
         xis: Sequence[float] = (0.0010, 0.0019, 0.0035), shrinks: Sequence[float] = (0.02, 0.08, 0.2)) -> dict:
    """Grid-search hyper-parameters by 1X2 log loss on the walk-forward window."""
    results = []
    for xi, sh in product(xis, shrinks):
        r = walk_forward(matches, start, FitConfig(xi=xi, shrinkage=sh), refit_days=14)
        if r.get("n"):
            results.append(r)
    best = min(results, key=lambda r: r["1x2"]["log_loss"])
    return {"best": best["config"], "grid": [{"config": r["config"], "log_loss": r["1x2"]["log_loss"],
                                              "brier": r["1x2"]["brier"]} for r in results]}
