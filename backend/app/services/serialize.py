"""Shared response shapes so the demo and live repositories return identical JSON."""
from __future__ import annotations


def prediction_summary(pred: dict | None) -> dict | None:
    if not pred:
        return None
    d = pred["display"]
    top1x2 = next(p for p in pred["picks"] if p["market"] == "1X2")
    return {
        "1x2": d["1x2"], "btts": d["btts"], "ou25": d["ou"]["2.5"],
        "xg": {"home": round(pred["rates"]["home"], 2), "away": round(pred["rates"]["away"], 2)},
        "confidence": pred["confidence"], "completeness": pred["completeness"]["score"],
        "top_pick": top1x2, "updated_at": pred["created_at"], "model_version": pred["model_version"],
    }


def fixture_out(*, id: int, league, kickoff_utc, status: str, status_long: str, elapsed, home: dict, away: dict,
                venue, city, round, goals, ft, demo: bool, prediction: dict | None) -> dict:
    return {
        "id": id, "league_slug": league.slug, "league_name": league.name, "country": league.country,
        "country_code": league.country_code, "kickoff_utc": kickoff_utc.isoformat(), "status": status,
        "status_long": status_long, "elapsed": elapsed, "home": home, "away": away, "venue": venue, "city": city,
        "round": round, "score": {"home": goals[0], "away": goals[1]}, "ft": {"home": ft[0], "away": ft[1]},
        "demo": demo, "prediction": prediction_summary(prediction),
    }


LIVE_STATUSES = {"1H", "HT", "2H", "ET", "P", "INT", "SUSP"}
FINAL_STATUSES = {"FT", "AET", "PEN"}
