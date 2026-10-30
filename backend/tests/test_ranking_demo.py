import json
from datetime import date, datetime, timedelta, timezone

import pytest

from app.model.ranking import summarize_settled, top_predictions
from app.services.demo import DemoRepository


@pytest.fixture(scope="module")
def demo():
    return DemoRepository(date(2026, 10, 30))


def test_every_demo_fixture_is_labelled(demo):
    for f in demo.fixtures_range(date(2026, 10, 16), 23):
        assert f["demo"] is True
    assert demo.health()["demo"] is True
    assert demo.analytics()["demo"] is True


def test_demo_predictions_created_before_kickoff(demo):
    for fid, p in demo.preds.items():
        assert datetime.fromisoformat(p["created_at"]) < datetime.fromisoformat(p["kickoff"])


def test_postponed_fixture_has_no_prediction_or_settlement(demo):
    pst = [f for f in demo.fixtures.values() if f["status"] == "PST"]
    for f in pst:
        assert f["id"] not in demo.preds
        assert not [s for s in demo.settled if s["fixture_id"] == f["id"]]


def test_no_guarantee_language_anywhere(demo):
    blob = json.dumps([demo.expls[k] for k in list(demo.expls)[:60]]).lower()
    for banned in ("guaranteed", "sure win", "100% safe", "risk-free", "lock"):
        assert banned not in blob


def test_top_predictions_sorted_and_filtered(demo):
    day = date(2026, 10, 31)
    rows = demo.top(day, market="OVER_2.5", min_p=0.4)
    assert all(r["market"] == "OU2.5" and r["selection"] == "Over" and r["p"] >= 0.4 for r in rows)
    scores = [r["score"] for r in rows]
    assert scores == sorted(scores, reverse=True)


def test_summary_windows():
    now = datetime(2026, 10, 30, tzinfo=timezone.utc)
    rows = [{"league_slug": "mls", "market": "1X2", "selection": "1", "probability": 0.6,
             "outcome": "won" if i % 2 else "lost", "settled_at": now - timedelta(days=i), "decimal_odds": 2.0}
            for i in range(60)]
    s = summarize_settled(rows, now)
    assert s["windows"]["7"]["n"] == 8      # days 0..7 inclusive of cutoff
    assert s["windows"]["90"]["n"] == 60
    assert s["windows"]["90"]["hypothetical_roi"]["roi"] == pytest.approx(0.0)
