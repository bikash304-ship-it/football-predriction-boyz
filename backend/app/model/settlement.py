"""Settle pre-match predictions against the official full-time (90 minute) result.

Rules
- Markets settle on the regulation-time score (API-Football `score.fulltime`), never on
  extra time or penalties. A cup-tie decided on penalties after 1-1 settles as a Draw.
- Postponed / cancelled / abandoned / awarded / walkover -> VOID.
- Any non-final status -> PENDING (nothing is settled early).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

FINAL_STATUSES = {"FT", "AET", "PEN"}
VOID_STATUSES = {"PST", "CANC", "ABD", "AWD", "WO"}


class Outcome(str, Enum):
    WON = "won"
    LOST = "lost"
    VOID = "void"
    PENDING = "pending"


@dataclass(frozen=True)
class FinalScore:
    status: str
    home_ft: int | None  # regulation-time goals
    away_ft: int | None


def actual_outcomes(score: FinalScore) -> dict[str, str] | None:
    """Return the actual result for every market, or None if not settleable yet/void."""
    if score.status not in FINAL_STATUSES or score.home_ft is None or score.away_ft is None:
        return None
    h, a = score.home_ft, score.away_ft
    res = {
        "1X2": "1" if h > a else ("2" if a > h else "X"),
        "BTTS": "Yes" if h > 0 and a > 0 else "No",
    }
    for line in (0.5, 1.5, 2.5, 3.5, 4.5):
        res[f"OU{line}"] = "Over" if h + a > line else "Under"
    return res


def settle_pick(market: str, selection: str, score: FinalScore) -> Outcome:
    if score.status in VOID_STATUSES:
        return Outcome.VOID
    actual = actual_outcomes(score)
    if actual is None:
        return Outcome.PENDING
    if market not in actual:
        raise ValueError(f"unknown market {market}")
    return Outcome.WON if actual[market] == selection else Outcome.LOST


def settle_all(picks: list[dict], score: FinalScore) -> list[dict]:
    return [{**p, "outcome": settle_pick(p["market"], p["selection"], score).value} for p in picks]


def outcome_vectors(score: FinalScore) -> dict[str, tuple] | None:
    """One-hot actual outcomes used by Brier/log-loss scoring."""
    actual = actual_outcomes(score)
    if actual is None:
        return None
    return {
        "1X2": tuple(1 if actual["1X2"] == k else 0 for k in ("1", "X", "2")),
        "BTTS": (1 if actual["BTTS"] == "Yes" else 0,),
        **{f"OU{l}": (1 if actual[f"OU{l}"] == "Over" else 0,) for l in (0.5, 1.5, 2.5, 3.5, 4.5)},
    }
