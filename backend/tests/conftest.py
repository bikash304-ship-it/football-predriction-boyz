"""Test fixtures. The synthetic league here is simulated from KNOWN parameters so we can
check the fitter recovers them. It is test data only and is never served by the app."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.model.dixon_coles import MatchResult  # noqa: E402

TRUE_ATTACK = {"A": 0.45, "B": 0.25, "C": 0.10, "D": 0.0, "E": -0.10, "F": -0.20, "G": -0.20, "H": -0.30}
TRUE_DEFENCE = {"A": -0.40, "B": -0.20, "C": -0.05, "D": 0.0, "E": 0.05, "F": 0.15, "G": 0.20, "H": 0.25}
TRUE_HOME = 0.25


def simulate_league(seasons: int = 3, seed: int = 1) -> list[MatchResult]:
    rng = np.random.default_rng(seed)
    teams = list(TRUE_ATTACK)
    start = datetime(2023, 8, 1, 15, tzinfo=timezone.utc)
    out, day = [], 0
    for _ in range(seasons):
        for h in teams:
            for a in teams:
                if h == a:
                    continue
                lam = np.exp(TRUE_ATTACK[h] + TRUE_DEFENCE[a] + TRUE_HOME)
                mu = np.exp(TRUE_ATTACK[a] + TRUE_DEFENCE[h])
                out.append(MatchResult(start + timedelta(days=day), h, a,
                                       int(rng.poisson(lam)), int(rng.poisson(mu))))
                day += 1
    return out


@pytest.fixture(scope="session")
def league():
    return simulate_league()
