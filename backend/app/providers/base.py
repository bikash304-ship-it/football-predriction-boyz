"""Provider-agnostic data contracts. Swap API-Football for Sportmonks (or anything else)
by implementing `FootballProvider`; nothing above this layer changes."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class TeamDTO:
    provider_id: int
    name: str
    short_name: str | None = None
    logo_url: str | None = None
    country: str | None = None


@dataclass
class FixtureDTO:
    provider_id: int
    league_provider_id: int
    season: int
    kickoff_utc: datetime            # timezone-aware, UTC
    status: str                      # normalised short code: NS, 1H, HT, 2H, ET, P, FT, AET, PEN, PST, CANC, ABD, AWD, WO, SUSP, INT, TBD
    status_long: str
    elapsed: int | None
    home: TeamDTO
    away: TeamDTO
    venue: str | None
    city: str | None
    round: str | None
    goals_home: int | None           # current/final incl. extra time
    goals_away: int | None
    ft_home: int | None              # regulation-time score (settlement uses this)
    ft_away: int | None
    raw: dict = field(default_factory=dict, repr=False)


@dataclass
class StandingDTO:
    team_provider_id: int
    rank: int
    points: int
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    form: str | None
    group: str | None                # conference / group, e.g. MLS Eastern/Western


@dataclass
class InjuryDTO:
    team_provider_id: int
    player: str
    type: str                        # e.g. "Missing Fixture", "Questionable"
    reason: str | None


@dataclass
class MatchStatsDTO:
    fixture_provider_id: int
    home_xg: float | None
    away_xg: float | None
    stats: dict


@dataclass
class OddsDTO:
    fixture_provider_id: int
    bookmaker: str
    market: str                      # "1X2", "BTTS", "OU2.5", ...
    selections: dict[str, float]     # decimal odds
    fetched_at: datetime


@dataclass
class LeagueCoverage:
    provider_id: int
    name: str
    country: str
    current_season: int | None
    fixtures: bool
    standings: bool
    injuries: bool
    lineups: bool
    statistics: bool
    odds: bool


class ProviderError(Exception):
    pass


class FootballProvider(ABC):
    name: str

    @abstractmethod
    async def coverage(self, league_id: int) -> LeagueCoverage: ...

    @abstractmethod
    async def fixtures(self, league_id: int, season: int, date_from: date, date_to: date) -> list[FixtureDTO]: ...

    @abstractmethod
    async def live_fixtures(self, league_ids: list[int]) -> list[FixtureDTO]: ...

    @abstractmethod
    async def fixture(self, fixture_id: int) -> FixtureDTO | None: ...

    @abstractmethod
    async def standings(self, league_id: int, season: int) -> list[StandingDTO]: ...

    @abstractmethod
    async def injuries(self, fixture_id: int) -> list[InjuryDTO]: ...

    @abstractmethod
    async def lineups(self, fixture_id: int) -> dict | None: ...

    @abstractmethod
    async def match_stats(self, fixture_id: int) -> MatchStatsDTO | None: ...

    async def odds(self, fixture_id: int) -> list[OddsDTO]:
        return []
