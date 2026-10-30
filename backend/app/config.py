"""Runtime configuration from environment variables (see ../.env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "Football Predriction Boyz"
    tagline: str = "Smart Predictions. Better Football Insights."
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    api_football_key: str = field(default_factory=lambda: os.getenv("API_FOOTBALL_KEY", ""))
    api_football_base: str = field(default_factory=lambda: os.getenv("API_FOOTBALL_BASE", "https://v3.football.api-sports.io"))
    api_requests_per_minute: int = field(default_factory=lambda: int(os.getenv("API_REQUESTS_PER_MINUTE", "250")))
    odds_enabled: bool = field(default_factory=lambda: _bool("ODDS_ENABLED"))
    admin_token: str = field(default_factory=lambda: os.getenv("ADMIN_TOKEN", ""))
    default_timezone: str = field(default_factory=lambda: os.getenv("DEFAULT_TIMEZONE", "Europe/Oslo"))
    cors_origins: tuple[str, ...] = field(default_factory=lambda: tuple(
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()))
    history_seasons: int = field(default_factory=lambda: int(os.getenv("HISTORY_SEASONS", "3")))

    @property
    def live_data_configured(self) -> bool:
        return bool(self.api_football_key and self.database_url)

    @property
    def demo_mode(self) -> bool:
        # Demo mode ONLY when live data is not configured. Never mixed with live data.
        return not self.live_data_configured


settings = Settings()
