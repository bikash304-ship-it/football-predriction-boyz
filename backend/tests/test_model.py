from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from app.model.dixon_coles import FitConfig, InsufficientDataError, fit, score_matrix
from app.model.markets import derive_markets, implied_probabilities, picks, to_percentages, bookmaker_margin
from app.model.predictor import predict_fixture
from app.model.explain import build_explanation, flatten, validate_llm_rewrite
from app.model.backtest import walk_forward
from tests.conftest import TRUE_ATTACK, TRUE_HOME


# ------------------------------------------------------------- score matrix / markets
@pytest.mark.parametrize("lam,mu,rho", [(1.5, 1.1, -0.08), (0.4, 0.3, 0.0), (3.2, 2.7, -0.03), (1.0, 1.0, 0.1)])
def test_matrix_is_a_distribution(lam, mu, rho):
    m = score_matrix(lam, mu, rho)
    assert np.all(m >= 0)
    assert m.sum() == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("lam,mu,rho", [(1.5, 1.1, -0.08), (0.6, 2.4, -0.05), (2.8, 0.7, 0.02)])
def test_markets_sum_to_one_and_are_consistent(lam, mu, rho):
    mk = derive_markets(score_matrix(lam, mu, rho))
    assert mk.home + mk.draw + mk.away == pytest.approx(1.0, abs=1e-12)
    assert mk.btts_yes + mk.btts_no == pytest.approx(1.0, abs=1e-12)
    for line in mk.over:
        assert mk.over[line] + mk.under[line] == pytest.approx(1.0, abs=1e-12)
    # Over lines must be monotonically decreasing.
    overs = [mk.over[k] for k in ("0.5", "1.5", "2.5", "3.5", "4.5")]
    assert all(x >= y for x, y in zip(overs, overs[1:]))
    # Cross-market identities: Under 0.5 is exactly P(0-0); BTTS Yes implies Over 1.5.
    m = score_matrix(lam, mu, rho)
    assert mk.under["0.5"] == pytest.approx(m[0, 0])
    assert mk.btts_yes <= mk.over["1.5"] + 1e-12


def test_pure_poisson_matches_closed_form():
    from scipy.stats import poisson
    lam, mu = 1.7, 1.2
    mk = derive_markets(score_matrix(lam, mu, 0.0))
    assert mk.btts_no == pytest.approx(poisson.pmf(0, lam) + poisson.pmf(0, mu) - poisson.pmf(0, lam) * poisson.pmf(0, mu), abs=1e-6)
    assert mk.under["2.5"] == pytest.approx(poisson.cdf(2, lam + mu), abs=1e-6)
    assert mk.expected_home_goals == pytest.approx(lam, abs=1e-4)


def test_negative_rho_inflates_draws():
    base = derive_markets(score_matrix(1.3, 1.1, 0.0))
    dc = derive_markets(score_matrix(1.3, 1.1, -0.1))
    assert dc.draw > base.draw


def test_percentages_always_total_100():
    for vals in ({"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}, {"a": 0.555, "b": 0.255, "c": 0.19}, {"y": 0.6349, "n": 0.3651}):
        assert sum(to_percentages(vals).values()) == 100


def test_picks_choose_the_maximum():
    mk = derive_markets(score_matrix(2.2, 0.6, -0.05))
    p = {x["market"]: x for x in picks(mk)}
    assert p["1X2"]["selection"] == "1"
    assert p["OU0.5"]["selection"] == "Over"


# ------------------------------------------------------------------- fitting
def test_fit_recovers_known_parameters():
    from tests.conftest import simulate_league
    big = simulate_league(seasons=8, seed=0)
    model = fit(big, as_of=big[-1].date + timedelta(days=1), config=FitConfig(xi=0.0, shrinkage=0.01))
    assert model.home_adv == pytest.approx(TRUE_HOME, abs=0.15)  # ~3 standard errors at this sample size
    for t, v in TRUE_ATTACK.items():
        assert model.attack[t] == pytest.approx(v, abs=0.25)
    order_true = sorted(TRUE_ATTACK, key=TRUE_ATTACK.get)
    order_fit = sorted(model.attack, key=model.attack.get)
    assert order_fit[-1] == order_true[-1]  # strongest attack identified
    assert sum(model.attack.values()) == pytest.approx(0.0, abs=1e-9)


def test_fit_ignores_future_matches(league):
    cutoff = league[100].date
    m1 = fit(league, as_of=cutoff)
    m2 = fit(league[:100], as_of=cutoff)
    assert m1.n_matches == m2.n_matches == 100
    assert m1.home_adv == pytest.approx(m2.home_adv, abs=1e-9)


def test_fit_refuses_tiny_samples(league):
    with pytest.raises(InsufficientDataError):
        fit(league[:10], as_of=league[10].date)


def test_fit_requires_aware_datetime(league):
    with pytest.raises(ValueError):
        fit(league, as_of=datetime(2030, 1, 1))


def test_unknown_team_defaults_to_league_average(league):
    model = fit(league, as_of=league[-1].date + timedelta(days=1))
    lam, mu = model.expected_goals("Promoted FC", "Also New")
    assert lam == pytest.approx(np.exp(model.home_adv))
    assert mu == pytest.approx(1.0)


# ---------------------------------------------------------------- full prediction
def test_predict_fixture_payload(league):
    ko = league[-1].date + timedelta(days=3)
    model = fit(league, as_of=ko)
    pred = predict_fixture(model, home="A", away="H", kickoff=ko, league_slug="premier-league", history=league)
    assert sum(pred["display"]["1x2"].values()) == 100
    assert pred["markets"]["home"] > pred["markets"]["away"]
    assert pred["model_version"]
    assert pred["context"]["injuries_status"] == "unavailable"
    assert any("Injury" in m for m in pred["completeness"]["missing"])
    lo, hi = pred["uncertainty"]["home"]
    assert lo <= pred["markets"]["home"] <= hi + 0.02


def test_explanation_is_grounded(league):
    ko = league[-1].date + timedelta(days=3)
    model = fit(league, as_of=ko)
    pred = predict_fixture(model, home="C", away="D", kickoff=ko, league_slug="mls", history=league)
    ex = build_explanation(pred)
    assert set(ex["sections"]) == {"home_case", "away_case", "draw", "btts", "goals", "key_stats", "risks"}
    text = flatten(ex)
    assert f"{pred['display']['1x2']['home']}%" in text
    assert "guarantee" not in text.lower().replace("not guarantees", "")
    for sec in ex["sections"].values():
        for s in sec:
            assert s["kind"] in ("fact", "model")


def test_llm_validator_rejects_invented_numbers():
    grounded = "Home win 56%. Expected goals 1.62."
    assert validate_llm_rewrite(grounded, "The hosts are 56% favourites with 1.62 expected goals.")
    assert not validate_llm_rewrite(grounded, "The hosts are 61% favourites.")


# -------------------------------------------------------------------- odds
def test_margin_removal():
    odds = {"1": 1.90, "X": 3.60, "2": 4.20}
    assert bookmaker_margin(odds) > 0
    for method in ("proportional", "power"):
        p = implied_probabilities(odds, method)
        assert sum(p.values()) == pytest.approx(1.0, abs=1e-9)
        assert p["1"] > p["X"] > p["2"]


# ----------------------------------------------------------------- backtest
def test_walk_forward_beats_baseline(league):
    start = league[len(league) // 2].date
    r = walk_forward(league, start, refit_days=21)
    assert r["n"] > 50
    assert 0 < r["1x2"]["brier"] < 1
    assert r["1x2"]["brier"] <= r["1x2"]["baseline_brier"] + 0.01
