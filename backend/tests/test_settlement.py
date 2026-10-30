import numpy as np
import pytest

from app.model.calibration import brier_binary, brier_multiclass, expected_calibration_error, log_loss_binary, reliability_bins
from app.model.settlement import FinalScore, Outcome, outcome_vectors, settle_all, settle_pick


@pytest.mark.parametrize("h,a,market,sel,expected", [
    (2, 1, "1X2", "1", Outcome.WON),
    (2, 1, "1X2", "X", Outcome.LOST),
    (1, 1, "1X2", "X", Outcome.WON),
    (0, 3, "1X2", "2", Outcome.WON),
    (1, 1, "BTTS", "Yes", Outcome.WON),
    (1, 0, "BTTS", "Yes", Outcome.LOST),
    (0, 0, "BTTS", "No", Outcome.WON),
    (0, 0, "OU0.5", "Under", Outcome.WON),
    (1, 0, "OU0.5", "Over", Outcome.WON),
    (2, 1, "OU2.5", "Over", Outcome.WON),
    (1, 1, "OU2.5", "Over", Outcome.LOST),
    (2, 2, "OU3.5", "Over", Outcome.WON),
    (3, 1, "OU4.5", "Under", Outcome.WON),
    (3, 2, "OU4.5", "Over", Outcome.WON),
])
def test_settlement_rules(h, a, market, sel, expected):
    assert settle_pick(market, sel, FinalScore("FT", h, a)) == expected


def test_penalty_shootout_settles_on_regulation_score():
    # 1-1 after 90, decided on penalties: the 90-minute markets see a draw.
    assert settle_pick("1X2", "X", FinalScore("PEN", 1, 1)) == Outcome.WON


@pytest.mark.parametrize("status", ["PST", "CANC", "ABD", "AWD", "WO"])
def test_void_statuses(status):
    assert settle_pick("1X2", "1", FinalScore(status, None, None)) == Outcome.VOID


@pytest.mark.parametrize("status", ["NS", "1H", "HT", "2H", "ET", "SUSP", "INT", "TBD"])
def test_unfinished_stays_pending(status):
    assert settle_pick("BTTS", "Yes", FinalScore(status, 1, 1)) == Outcome.PENDING


def test_settle_all_keeps_pick_fields():
    out = settle_all([{"market": "1X2", "selection": "1", "p": 0.55}], FinalScore("FT", 3, 0))
    assert out == [{"market": "1X2", "selection": "1", "p": 0.55, "outcome": "won"}]


def test_unknown_market_raises():
    with pytest.raises(ValueError):
        settle_pick("Corners", "Over", FinalScore("FT", 1, 0))


def test_outcome_vectors():
    v = outcome_vectors(FinalScore("FT", 0, 2))
    assert v["1X2"] == (0, 0, 1) and v["BTTS"] == (0,) and v["OU1.5"] == (1,)


# --------------------------------------------------------------- scoring rules
def test_brier_and_logloss_known_values():
    assert brier_multiclass(np.array([[1, 0, 0]]), np.array([[1, 0, 0]])) == 0
    assert brier_multiclass(np.array([[0, 1, 0]]), np.array([[1, 0, 0]])) == 2
    assert brier_binary([0.7], [1]) == pytest.approx(0.09)
    assert log_loss_binary([0.5], [1]) == pytest.approx(np.log(2))


def test_perfectly_calibrated_forecasts_have_low_ece():
    rng = np.random.default_rng(0)
    p = rng.uniform(0, 1, 20000)
    y = rng.uniform(0, 1, 20000) < p
    assert expected_calibration_error(p, y) < 0.02
    bins = reliability_bins(p, y)
    assert sum(b["count"] for b in bins) == 20000
