"""The six supported competitions.

`provider_id` values are API-Football v3 league IDs. They are verified at runtime by
`scripts/verify_coverage.py`, which calls /leagues?id=<id>&current=true and checks the
name, country and coverage flags for YOUR subscription before any sync runs.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class League:
    slug: str
    name: str
    country: str
    country_code: str      # ISO-3166 alpha-2 for the flag emoji/icon
    provider_id: int
    calendar_year_season: bool  # True for Eliteserien and MLS (season == calendar year)
    has_playoffs: bool
    expected_name: str     # name the provider must return, used for verification


LEAGUES: tuple[League, ...] = (
    League("premier-league", "Premier League", "England", "GB-ENG", 39, False, False, "Premier League"),
    League("la-liga", "La Liga", "Spain", "ES", 140, False, False, "La Liga"),
    League("bundesliga", "Bundesliga", "Germany", "DE", 78, False, False, "Bundesliga"),
    League("ligue-1", "Ligue 1", "France", "FR", 61, False, False, "Ligue 1"),
    League("eliteserien", "Eliteserien", "Norway", "NO", 103, True, True, "Eliteserien"),
    League("mls", "Major League Soccer", "USA & Canada", "US", 253, True, True, "Major League Soccer"),
)

BY_SLUG = {l.slug: l for l in LEAGUES}
BY_PROVIDER_ID = {l.provider_id: l for l in LEAGUES}
