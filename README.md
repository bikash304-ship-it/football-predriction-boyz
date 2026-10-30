# Football Predriction Boyz

**Smart Predictions. Better Football Insights.**

A data-driven football prediction platform for the **Premier League, La Liga, Bundesliga, Ligue 1, Eliteserien and MLS**. Every upcoming match gets 1X2, BTTS and Over/Under 0.5–4.5 probabilities from a real statistical model, a grounded English explanation, and an immutable pre-match record that is settled automatically after the final whistle.

```
football-predriction-boyz/
├── backend/                 Python 3.12 · FastAPI · PostgreSQL · APScheduler
│   ├── app/model/           Dixon-Coles engine, markets, settlement, calibration, backtest, explanations, ranking
│   ├── app/providers/       Provider adapter layer (API-Football v3 implemented)
│   ├── app/services/        Sync/predict/settle jobs, live + demo repositories
│   ├── app/api/main.py      REST API
│   ├── app/scheduler.py     Background worker (runs without anyone visiting the site)
│   ├── migrations/          SQL migrations (append-only predictions enforced by trigger)
│   ├── scripts/             verify_coverage.py, backtest.py
│   └── tests/               60 tests: probabilities, market consistency, settlement, scoring, demo honesty
├── frontend/                Next.js 15 · React 19 · TypeScript · Tailwind · Recharts
└── docker-compose.yml       db + api + worker + web
```

---

## Quick start (demo mode, 2 minutes)

Demo mode runs automatically when `API_FOOTBALL_KEY` or `DATABASE_URL` is missing. It uses **fictional clubs and simulated results**, every element is tagged **DEMO**, and a banner is shown on every page. The probabilities are still produced by the real model (fitted only on data before each kickoff), so every page, chart and settlement works end to end.

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                                   # 60 passed
uvicorn app.api.main:app --reload --port 8000

# frontend (second terminal)
cd frontend
npm install
BACKEND_URL=http://localhost:8000 npm run dev     # http://localhost:3000
```

## Going live with real data

1. **Get an API-Football key** (https://www.api-football.com). Football data for six leagues, live scores, injuries and lineups needs a paid plan; check yours includes all six leagues.
2. `cp .env.example .env` and set `API_FOOTBALL_KEY`, `DATABASE_URL`, `ADMIN_TOKEN`, `API_REQUESTS_PER_MINUTE`.
3. **Verify coverage for your subscription before syncing:**
   ```bash
   cd backend && API_FOOTBALL_KEY=... python -m scripts.verify_coverage
   ```
   This calls `/leagues?id=…&current=true` for each league, confirms the name matches (IDs: EPL 39, La Liga 140, Bundesliga 78, Ligue 1 61, Eliteserien 103, MLS 253 — set in `app/leagues.py`), resolves the current season, and prints which of fixtures / standings / injuries / lineups / statistics (xG) / odds your plan covers. The worker runs the same check every night and refuses to sync a league whose ID returns the wrong competition.
4. Start everything: `docker compose up --build` (or run `uvicorn` + `python -m app.scheduler` + `npm start` yourself). Migrations apply automatically.
5. First run pulls `HISTORY_SEASONS` (default 3) seasons per league, fits the models, and publishes predictions. A league with fewer than 30 verified completed matches is **skipped, not guessed**.
6. Optional: `python -m scripts.backtest --league premier-league --start 2025-08-01 --tune` for a walk-forward backtest; results appear on the Analytics page.

### Automatic schedule (worker, UTC)

| Job | When | What |
|---|---|---|
| fixtures | hourly :05 | yesterday → +8 days, status changes (postponed / cancelled / suspended) |
| live | every 45 s | live scores — makes **no API calls** unless a match is live or about to start |
| context | every 15 min | injuries 48 h out (if covered), lineups ~75 min before kickoff |
| predict | every 30 min | refit + append a new prediction only if probabilities move ≥1 pt or team news changes |
| settle | every 10 min | settle the official pre-match prediction on the 90-minute score |
| odds | every 2 h | only with `ODDS_ENABLED=true` |
| daily | 04:15 | coverage → fixtures → full history, standings, xG → context → predict → settle |

Admins can trigger any job from **Settings → Administrator** with `ADMIN_TOKEN`.

---

## The model

* **Dixon-Coles** goal model per league: team attack/defence ratings, home advantage, and the low-score dependence parameter ρ, fitted by weighted maximum likelihood.
* **Recency weighting** `exp(-ξ·days)` and **L2 shrinkage** toward the league mean, so a promoted side with five matches isn't rated a giant. Unknown teams default to league average.
* **xG blending** when ≥60% of a league's matches have xG from the provider; otherwise goals only (disclosed).
* **Small bounded adjustments** (each ≤5%, total ≤10%) for short rest, fixture congestion and MLS back-to-back road trips. Every adjustment is listed on the match page.
* **One score matrix → every market.** 1X2, BTTS, Over/Under 0.5–4.5, correct scores and expected goals are all sums over the same 11×11 distribution, so they cannot contradict each other (tests assert e.g. `P(Under 0.5) = P(0-0)` and `P(BTTS Yes) ≤ P(Over 1.5)`). Displayed percentages use largest-remainder rounding so they always total exactly 100.
* **Uncertainty**: Monte Carlo over rating standard errors gives an 80% range for each 1X2 outcome; combined with data completeness this sets the High / Medium / Low confidence label.
* **Calibration & backtesting**: walk-forward evaluation that only ever fits on matches before the test date; ξ and shrinkage are tuned by log loss. Calibration is done at the goal-model level (not by distorting individual market probabilities) so consistency is preserved. Brier, log loss, ECE and reliability curves are tracked live by league and market.
* **Head-to-head** is shown but deliberately given no special weight.
* **Injuries** are shown when the provider verifies them but are not converted into numbers (without per-player value data that would be guesswork) — the explanation says so.

### Explanations

Built deterministically from the prediction payload, seven sections (home case, away case, draw, BTTS, goals, key stats, what could go wrong). Every sentence is tagged **Fact** (retrieved statistic) or **Model** (estimate). If `ANTHROPIC_API_KEY` is set, Claude may rewrite it into smoother prose, but the rewrite is **rejected unless every number in it already appears in the grounded text**, and any guarantee-style wording is blocked.

### Honesty guarantees (enforced in code)

* Predictions table is **append-only** — a PostgreSQL trigger rejects UPDATE/DELETE, and a CHECK constraint rejects any prediction created after kickoff. Settlement lives in a separate table. Payloads carry a SHA-256 hash.
* No random numbers are ever used as probabilities; no fixtures, scores or injuries are invented; demo data is only served when live data isn't configured and is never mixed with it.
* If a sync fails, the API keeps serving the last verified data and the UI shows a warning with the failure time.
* No "guaranteed / sure win / safe" language anywhere (tested).

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | mode (demo/live), last successful sync per job, warnings |
| `GET /api/leagues`, `/api/leagues/{slug}` | leagues, standings, fixtures |
| `GET /api/fixtures?date=YYYY-MM-DD&tz=Europe/Oslo&league=` | a day's fixtures with prediction summaries |
| `GET /api/fixtures/week`, `/api/fixtures/live`, `/api/fixtures/{id}` | next 8 days, live, full match analysis |
| `GET /api/predictions/top?date=&market=1X2\|BTTS\|OVER_1.5\|OVER_2.5\|UNDER_2.5\|OVER_3.5&league=&min_p=` | ranked top predictions |
| `GET /api/analytics`, `/api/history` | performance & settled predictions |
| `GET /api/search?q=` | clubs and matches |
| `POST /api/admin/refresh?job=all` | manual refresh (`X-Admin-Token`) |

The browser never talks to the backend directly: Next.js server components call it with `BACKEND_URL`, and `/api/proxy/*` exposes only read endpoints plus admin refresh. API keys stay server-side.

## Deployment

**Single VPS / any Docker host:** `docker compose up -d --build` behind a reverse proxy (Caddy/Nginx) for HTTPS.

**Free setup (what this repository is configured for):**
* Website + API: Vercel Hobby (two projects: `frontend/` and `backend/`).
* Database: Supabase free (use the **session pooler** connection string, port 5432).
* Scheduled jobs: GitHub Actions (`.github/workflows/scheduled-jobs.yml`) — live scores and settlement every 10 min, fixtures/team news/predictions hourly, full refresh daily at 04:15 UTC. Add repository secrets `API_FOOTBALL_KEY` and `DATABASE_URL`. Run it by hand from **Actions → Scheduled jobs → Run workflow**.
* While a match is live and someone has the app open, the API also refreshes scores itself, at most once a minute.

**Managed split (always-on worker):**
* Postgres: Supabase, Neon or Railway.
* Backend API **and** worker: Railway / Render / Fly.io — two services from `backend/` (`uvicorn app.api.main:app --host 0.0.0.0 --port $PORT` and `python -m app.scheduler`). The worker must be an always-on service, not a serverless function.
* Frontend: Vercel (root `frontend/`, env `BACKEND_URL`) or the included Dockerfile.

Security checklist: set a long random `ADMIN_TOKEN`; restrict `CORS_ORIGINS`; keep the database private to the API/worker; rotate the API key if it's ever exposed.

## On your iPhone

Football Predriction Boyz is a web app with an app manifest and iPhone icon, so it installs to the home screen:

1. Deploy it (see Deployment) so it has a public HTTPS address.
2. Open that address in **Safari** on the iPhone.
3. Tap **Share** → **Add to Home Screen** → **Add**.

It then opens full-screen from its own icon, with the dark theme and status bar. Prediction alerts work while the app is open; background push notifications on iOS would need a push service added later.

## Tests

```bash
cd backend && pytest          # model, markets, settlement, scoring rules, ranking, demo honesty
cd frontend && npm test       # timezone/DST and label tests (vitest)
```

## Responsible use

Probabilities are estimates, not guarantees, and a high probability is not the same as value against bookmaker prices. Hypothetical ROI is only shown when real stored pre-kickoff odds exist, with the assumptions printed next to it. Help with gambling problems in Norway: Hjelpelinjen 800 800 40.
