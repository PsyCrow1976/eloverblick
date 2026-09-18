# Web interface

A small [FastHTML](https://fastht.ml) app that stores ElOverblik usage in an existing PostgreSQL database and lets you browse hours, days, months, and years that already have data.

Run from the repository root. Python code for the Customer API stays in `script/`. This app lives in `web/`.

## Layout

| Path | Role |
| --- | --- |
| `web/app.py` | FastHTML routes and pages |
| `web/db.py` | PostgreSQL schema and queries |
| `web/ingest.py` | Pulls Customer API usage into the tables |
| `web/prices.py` | Day-ahead hourly prices from Energi Data Service |
| `web/jobs.py` | In-process 6-hour price job, file + database logging |
| `web/__main__.py` | `python -m web` |
| `Dockerfile` / `docker-compose.yml` | Unraid / Docker deploy |
| `.env.example` | Environment template |

## Environment

Copy `.env.example` to `.env` (gitignored). Required:

- `ELOVERBLIK_TOKEN` — Customer API refresh token
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`

PostgreSQL is **not** started by compose. Point the variables at the server you already run (Unraid, VM, or LAN host).

On startup the app creates schema `eloverblick` and these tables:

- `eloverblick.metering_points`
- `eloverblick.hours` — one row per hour, with `scraped_at`
- `eloverblick.days` — calendar day total, with `scraped_at`
- `eloverblick.months` — calendar month total, with `scraped_at`
- `eloverblick.years` — calendar year total, with `scraped_at`
- `eloverblick.hour_prices` — hourly day-ahead spot prices (DKK/MWh and EUR/MWh), with `scraped_at`
- `eloverblick.job_logs` — each job run: timestamp, instance name, success/fail, output
- `eloverblick.job_state` — whether the price job is enabled, interval, last run

Optional:

- `PRICE_AREA` — bidding zone, default `DK2` (east Denmark / Copenhagen). Use `DK1` for west Denmark.
- `JOB_INTERVAL_HOURS` — default `6`
- `USAGE_LOOKBACK_DAYS` — completed days behind today to backfill, default `3`
- `JOB_LOG_PATH` — default `/var/log/eloverblick/prices.log` in Docker; locally falls back to `logs/prices.log` if that path is not writable
- `JOB_INSTANCE` — name written on each log row; defaults to the container hostname

## Scheduled job

On container start the app starts a background job (not system cron). Every 6 hours it:

1. Pulls day-ahead prices for **today and tomorrow** from [Energi Data Service DayAheadPrices](https://www.energidataservice.dk/tso-electricity/DayAheadPrices), averages 15-minute values to hours, and upserts `eloverblick.hour_prices`.
2. Checks the last `USAGE_LOOKBACK_DAYS` **completed** days (yesterday back). Days that already have at least 23 hourly usage rows are skipped. Missing or incomplete days are queried from ElOverblik and stored if DataHub has them.

Usage is typically 2–3 days behind. If a day is not settled yet, the run logs that it is pending and tries again next time. That is not treated as a job failure.

Each run writes:

1. A line in the log file (`OK` or `FAIL`, instance, output)
2. A row in `eloverblick.job_logs`

Tomorrow’s prices are usually published around 13:00 Copenhagen time. A run before that still stores today and logs that tomorrow is not published yet.

Open **Jobs** in the web UI (`/jobs`) to:

- See whether the job is running
- Start or stop it (stop is remembered across container restarts)
- Run a pull immediately
- Read the PostgreSQL log

Day pages also show the hourly spot price next to usage when prices exist for that date.

## Get data

- **Day** (`/YYYY/MM/DD`): pulls the day total **and** that day's hours from the API.
- If that day is already stored, the app asks whether to pull again before replacing the day total and hourly rows.
- **Month**: pulls daily totals for the month (does not replace hours already stored).
- **Year**: pulls monthly totals for the year.

## Run locally

```bash
cp .env.example .env
# fill in token and Postgres settings
python -m web
```

Open http://127.0.0.1:8080

## Docker / Unraid

Unraid steps (Compose Manager, appdata path, `.env`, Postgres host) are in [deploy.md](deploy.md).

```bash
docker compose up -d --build
```

The container listens on `WEB_PORT` from `.env` (default `8080`). Set `POSTGRES_HOST` to an address the container can reach (on Unraid that is often the LAN IP of the Postgres container, e.g. `192.168.1.80`).
