# Web interface

A small [FastHTML](https://fastht.ml) app that stores ElOverblik usage in an existing PostgreSQL database and lets you browse hours, days, months, and years that already have data.

Run from the repository root. Python code for the Customer API stays in `script/`. This app lives in `web/`.

## Layout

| Path | Role |
| --- | --- |
| `web/app.py` | FastHTML routes and pages |
| `web/db.py` | PostgreSQL schema and queries |
| `web/ingest.py` | Pulls Customer API usage into the tables |
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

Open http://127.0.0.1:5001

## Docker / Unraid

Unraid steps (Compose Manager, appdata path, `.env`, Postgres host) are in [deploy.md](deploy.md).

```bash
docker compose up -d --build
```

The container listens on port `5001`. Set `POSTGRES_HOST` to an address the container can reach (on Unraid that is often the LAN IP of the Postgres container, e.g. `192.168.1.130`).
