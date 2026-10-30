-- Football Predriction Boyz — initial schema (PostgreSQL 14+)
-- All timestamps are TIMESTAMPTZ (stored in UTC). Provider IDs are stable external keys.

CREATE TABLE leagues (
    id              SERIAL PRIMARY KEY,
    slug            TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    country         TEXT NOT NULL,
    country_code    TEXT NOT NULL,
    provider        TEXT NOT NULL DEFAULT 'api-football',
    provider_id     INTEGER NOT NULL,
    logo_url        TEXT,
    coverage        JSONB,                 -- verified coverage flags for the subscription
    coverage_checked_at TIMESTAMPTZ,
    UNIQUE (provider, provider_id)
);

CREATE TABLE seasons (
    id          SERIAL PRIMARY KEY,
    league_id   INTEGER NOT NULL REFERENCES leagues(id),
    year        INTEGER NOT NULL,
    is_current  BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (league_id, year)
);

CREATE TABLE teams (
    id          SERIAL PRIMARY KEY,
    provider    TEXT NOT NULL DEFAULT 'api-football',
    provider_id INTEGER NOT NULL,
    name        TEXT NOT NULL,
    short_name  TEXT,
    logo_url    TEXT,
    country     TEXT,
    UNIQUE (provider, provider_id)
);
CREATE INDEX teams_name_trgm ON teams (lower(name));

CREATE TABLE fixtures (
    id              SERIAL PRIMARY KEY,
    provider        TEXT NOT NULL DEFAULT 'api-football',
    provider_id     INTEGER NOT NULL,
    league_id       INTEGER NOT NULL REFERENCES leagues(id),
    season_year     INTEGER NOT NULL,
    round           TEXT,
    kickoff_utc     TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL,          -- NS, 1H, HT, 2H, ET, P, FT, AET, PEN, PST, CANC, ABD, AWD, WO, SUSP, INT, TBD
    status_long     TEXT,
    elapsed         INTEGER,
    home_team_id    INTEGER NOT NULL REFERENCES teams(id),
    away_team_id    INTEGER NOT NULL REFERENCES teams(id),
    venue           TEXT,
    city            TEXT,
    goals_home      INTEGER,
    goals_away      INTEGER,
    ft_home         INTEGER,                -- regulation-time score, used for settlement
    ft_away         INTEGER,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_id)
);
CREATE INDEX fixtures_kickoff ON fixtures (kickoff_utc);
CREATE INDEX fixtures_league_kickoff ON fixtures (league_id, kickoff_utc);
CREATE INDEX fixtures_status ON fixtures (status);

CREATE TABLE match_statistics (
    fixture_id  INTEGER PRIMARY KEY REFERENCES fixtures(id),
    home_xg     DOUBLE PRECISION,
    away_xg     DOUBLE PRECISION,
    stats       JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE standings (
    league_id   INTEGER NOT NULL REFERENCES leagues(id),
    season_year INTEGER NOT NULL,
    team_id     INTEGER NOT NULL REFERENCES teams(id),
    rank        INTEGER NOT NULL,
    points      INTEGER NOT NULL,
    played      INTEGER NOT NULL,
    won INTEGER, drawn INTEGER, lost INTEGER,
    goals_for INTEGER, goals_against INTEGER,
    form        TEXT,
    group_name  TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (league_id, season_year, team_id)
);

CREATE TABLE fixture_context (           -- injuries / lineups, refreshed before kickoff
    fixture_id          INTEGER PRIMARY KEY REFERENCES fixtures(id),
    injuries            JSONB,           -- NULL = not checked / unavailable; [] = checked, none reported
    injuries_checked_at TIMESTAMPTZ,
    lineups             JSONB,           -- NULL = not confirmed
    lineups_checked_at  TIMESTAMPTZ
);

CREATE TABLE odds_snapshots (
    id          BIGSERIAL PRIMARY KEY,
    fixture_id  INTEGER NOT NULL REFERENCES fixtures(id),
    bookmaker   TEXT NOT NULL,
    market      TEXT NOT NULL,
    selections  JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX odds_fixture ON odds_snapshots (fixture_id, fetched_at DESC);

CREATE TABLE model_versions (
    id          SERIAL PRIMARY KEY,
    version     TEXT NOT NULL,
    league_id   INTEGER NOT NULL REFERENCES leagues(id),
    fitted_at   TIMESTAMPTZ NOT NULL,
    n_matches   INTEGER NOT NULL,
    params      JSONB NOT NULL,          -- attack/defence/home_adv/rho/config
    backtest    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX model_versions_league ON model_versions (league_id, created_at DESC);

-- Predictions are APPEND-ONLY. A recalculation inserts a new row; nothing is ever updated.
-- The "official" pre-match prediction is the latest row with created_at < kickoff.
CREATE TABLE predictions (
    id                BIGSERIAL PRIMARY KEY,
    fixture_id        INTEGER NOT NULL REFERENCES fixtures(id),
    model_version_id  INTEGER NOT NULL REFERENCES model_versions(id),
    model_version     TEXT NOT NULL,
    kind              TEXT NOT NULL DEFAULT 'pre_match' CHECK (kind IN ('pre_match')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    kickoff_utc       TIMESTAMPTZ NOT NULL,
    data_source       TEXT NOT NULL,
    input_freshness   JSONB NOT NULL,     -- timestamps of the data the prediction used
    p_home DOUBLE PRECISION NOT NULL, p_draw DOUBLE PRECISION NOT NULL, p_away DOUBLE PRECISION NOT NULL,
    p_btts_yes DOUBLE PRECISION NOT NULL,
    p_over JSONB NOT NULL,                -- {"0.5": .., "1.5": .., ...}
    xg_home DOUBLE PRECISION NOT NULL, xg_away DOUBLE PRECISION NOT NULL,
    confidence        TEXT NOT NULL,
    completeness      DOUBLE PRECISION NOT NULL,
    payload           JSONB NOT NULL,     -- full prediction (markets, picks, matrix, context)
    payload_sha256    TEXT NOT NULL,      -- integrity hash of payload
    CHECK (abs(p_home + p_draw + p_away - 1) < 1e-6),
    CHECK (created_at < kickoff_utc)      -- a pre-match prediction cannot be created after kickoff
);
CREATE INDEX predictions_fixture ON predictions (fixture_id, created_at DESC);

CREATE OR REPLACE FUNCTION forbid_prediction_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'predictions are immutable (attempted % on id %)', TG_OP, OLD.id;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER predictions_immutable
    BEFORE UPDATE OR DELETE ON predictions
    FOR EACH ROW EXECUTE FUNCTION forbid_prediction_mutation();

CREATE TABLE prediction_explanations (
    prediction_id BIGINT PRIMARY KEY REFERENCES predictions(id),
    explanation   JSONB NOT NULL,
    source        TEXT NOT NULL,           -- deterministic | deterministic+llm
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Settlement lives in its own table so the prediction row is never touched.
CREATE TABLE prediction_settlements (
    prediction_id BIGINT NOT NULL REFERENCES predictions(id),
    market        TEXT NOT NULL,           -- 1X2, BTTS, OU0.5 ... OU4.5
    selection     TEXT NOT NULL,
    probability   DOUBLE PRECISION NOT NULL,
    outcome       TEXT NOT NULL CHECK (outcome IN ('won', 'lost', 'void')),
    brier         DOUBLE PRECISION,
    log_loss      DOUBLE PRECISION,
    decimal_odds  DOUBLE PRECISION,        -- closing odds snapshot if available (hypothetical ROI only)
    final_home    INTEGER, final_away INTEGER,
    settled_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (prediction_id, market)
);

CREATE TABLE sync_logs (
    id          BIGSERIAL PRIMARY KEY,
    job         TEXT NOT NULL,
    started_at  TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    ok          BOOLEAN,
    items       INTEGER,
    error       TEXT,
    details     JSONB
);
CREATE INDEX sync_logs_job ON sync_logs (job, started_at DESC);

CREATE TABLE user_preferences (
    user_id          TEXT PRIMARY KEY,     -- anonymous device id or auth subject
    timezone         TEXT NOT NULL DEFAULT 'Europe/Oslo',
    theme            TEXT NOT NULL DEFAULT 'dark',
    odds_format      TEXT NOT NULL DEFAULT 'decimal',
    favorite_leagues TEXT[] NOT NULL DEFAULT '{}',
    favorite_teams   INTEGER[] NOT NULL DEFAULT '{}',
    notifications    BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE watchlists (
    user_id    TEXT NOT NULL,
    fixture_id INTEGER NOT NULL REFERENCES fixtures(id),
    added_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, fixture_id)
);
