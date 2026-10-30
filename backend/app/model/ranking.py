"""Ranking for "Today's Top Predictions" and aggregation for the analytics pages.

Ranking score = p_selection
              * sqrt(data_completeness)
              * (1 - historical calibration error for that league+market)   [0.9 when < 50 settled]
              * (1 - 0.5 * width of the 80% uncertainty band)              [1X2 only]

High score means "the model is fairly sure AND we trust the inputs". It says nothing
about value against bookmaker prices — see markets.expected_value for that.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from math import log, sqrt
from typing import Iterable

from .calibration import expected_calibration_error, reliability_bins

MARKET_FILTERS = {
    "1X2": lambda p: p["market"] == "1X2",
    "BTTS": lambda p: p["market"] == "BTTS",
    "OVER_1.5": lambda p: p["market"] == "OU1.5" and p["selection"] == "Over",
    "OVER_2.5": lambda p: p["market"] == "OU2.5" and p["selection"] == "Over",
    "UNDER_2.5": lambda p: p["market"] == "OU2.5" and p["selection"] == "Under",
    "OVER_3.5": lambda p: p["market"] == "OU3.5" and p["selection"] == "Over",
}


def candidate_selections(pred: dict) -> list[dict]:
    """Every selection we let users rank (both sides of OU lines, not only the top pick)."""
    mk = pred["markets"]
    out = [{"market": "1X2", "selection": k, "p": v} for k, v in (("1", mk["home"]), ("X", mk["draw"]), ("2", mk["away"]))]
    out += [{"market": "BTTS", "selection": "Yes", "p": mk["btts_yes"]}, {"market": "BTTS", "selection": "No", "p": mk["btts_no"]}]
    for line in ("1.5", "2.5", "3.5"):
        out += [{"market": f"OU{line}", "selection": "Over", "p": mk["over"][line]},
                {"market": f"OU{line}", "selection": "Under", "p": mk["under"][line]}]
    return out


def rank_score(sel: dict, pred: dict, calib_error: float | None) -> float:
    comp = pred["completeness"]["score"]
    cal = 0.9 if calib_error is None else max(0.5, 1 - calib_error)
    unc = 1.0
    if sel["market"] == "1X2":
        key = {"1": "home", "X": "draw", "2": "away"}[sel["selection"]]
        lo, hi = pred["uncertainty"][key]
        unc = 1 - 0.5 * (hi - lo)
    return sel["p"] * sqrt(comp) * cal * unc


def top_predictions(items: Iterable[dict], *, market: str | None = None, min_p: float = 0.0,
                    calib: dict[tuple[str, str], float] | None = None, limit: int = 20) -> list[dict]:
    """items: [{"fixture": {...}, "prediction": payload}] -> ranked selections, one per fixture+market."""
    calib = calib or {}
    rows = []
    for it in items:
        pred, fx = it["prediction"], it["fixture"]
        best_per_market: dict[str, dict] = {}
        for sel in candidate_selections(pred):
            if market and not MARKET_FILTERS[market](sel):
                continue
            if sel["p"] < min_p:
                continue
            fam = "OU" if sel["market"].startswith("OU") else sel["market"]
            err = calib.get((fx["league_slug"], fam))
            score = rank_score(sel, pred, err)
            cur = best_per_market.get(sel["market"])
            if not cur or score > cur["score"]:
                best_per_market[sel["market"]] = {**sel, "score": score, "fixture": fx,
                                                  "confidence": pred["confidence"],
                                                  "completeness": pred["completeness"]["score"]}
        rows.extend(best_per_market.values())
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:limit]


def summarize_settled(rows: list[dict], now: datetime) -> dict:
    """rows: settled selections {league_slug, market, selection, probability, outcome, settled_at(datetime), decimal_odds}"""
    def agg(rs: list[dict]) -> dict:
        rs = [r for r in rs if r["outcome"] in ("won", "lost")]
        n = len(rs)
        if not n:
            return {"n": 0}
        y = [1.0 if r["outcome"] == "won" else 0.0 for r in rs]
        p = [r["probability"] for r in rs]
        brier = sum((pi - yi) ** 2 for pi, yi in zip(p, y)) / n
        ll = -sum(yi * log(max(pi, 1e-12)) + (1 - yi) * log(max(1 - pi, 1e-12)) for pi, yi in zip(p, y)) / n
        odds_rs = [r for r in rs if r.get("decimal_odds")]
        roi = None
        if odds_rs:
            stake = len(odds_rs)
            ret = sum(r["decimal_odds"] for r in odds_rs if r["outcome"] == "won")
            roi = {"bets": stake, "profit_units": ret - stake, "roi": (ret - stake) / stake}
        return {"n": n, "hit_rate": sum(y) / n, "avg_probability": sum(p) / n, "brier": brier, "log_loss": ll,
                "ece": expected_calibration_error(p, y) if n >= 20 else None, "hypothetical_roi": roi}

    out = {"windows": {}, "by_league": {}, "by_market": {}, "calibration": None}
    for days in (7, 30, 90):
        cutoff = now - timedelta(days=days)
        out["windows"][str(days)] = agg([r for r in rows if r["settled_at"] >= cutoff])
    by_l, by_m = defaultdict(list), defaultdict(list)
    for r in rows:
        by_l[r["league_slug"]].append(r)
        by_m[r["market"]].append(r)
    out["by_league"] = {k: agg(v) for k, v in by_l.items()}
    out["by_market"] = {k: agg(v) for k, v in sorted(by_m.items())}
    decided = [r for r in rows if r["outcome"] in ("won", "lost")]
    if decided:
        out["calibration"] = reliability_bins([r["probability"] for r in decided],
                                              [1.0 if r["outcome"] == "won" else 0.0 for r in decided])
    return out


def calibration_errors(rows: list[dict], min_n: int = 50) -> dict[tuple[str, str], float]:
    groups = defaultdict(list)
    for r in rows:
        if r["outcome"] in ("won", "lost"):
            fam = "OU" if r["market"].startswith("OU") else r["market"]
            groups[(r["league_slug"], fam)].append(r)
    return {k: expected_calibration_error([r["probability"] for r in v],
                                          [1.0 if r["outcome"] == "won" else 0.0 for r in v])
            for k, v in groups.items() if len(v) >= min_n}
