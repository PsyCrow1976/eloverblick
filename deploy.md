# Deploy on Unraid

This stack is a single FastHTML container. PostgreSQL is **not** part of the compose file. Point `.env` at the Postgres server you already run.

The compose file uses `build: .`, so Unraid needs the GitHub repo on disk (Dockerfile, `script/`, `web/`). Pasting only `docker-compose.yml` into Compose Manager is not enough.

GitHub: https://github.com/PsyCrow1976/eloverblick

## What you need

- Unraid 6.10 or later, Docker enabled
- [Community Applications](https://unraid.net/community/apps)
- Postgres already running, reachable from Docker containers (LAN IP and published port, not `localhost`)
- `ELOVERBLIK_TOKEN` from [eloverblik.dk](https://eloverblik.dk) (Data → Access to data / API)

## 1. Install Compose Manager

1. Open the **Apps** tab.
2. Search for **Compose Manager Plus** (or **Docker Compose Manager** on older CA listings).
3. Install the plugin.
4. Open the **Docker** tab. A **Compose** section should appear.

The original Docker Compose Manager plugin is deprecated; Compose Manager Plus is the drop-in replacement.

## 2. Put the project on the array

Do not store the stack on the Unraid USB stick. Use appdata.

In the Unraid terminal:

```bash
mkdir -p /mnt/user/appdata/eloverblick
cd /mnt/user/appdata/eloverblick
git clone https://github.com/PsyCrow1976/eloverblick.git .
```

If `git` is not installed, download the repo ZIP from GitHub, extract it, and copy the files into `/mnt/user/appdata/eloverblick` so that `Dockerfile` and `docker-compose.yml` sit in that folder.

You should see at least:

- `docker-compose.yml`
- `Dockerfile`
- `requirements.txt`
- `.env.example`
- `script/`
- `web/`

## 3. Create `.env`

```bash
cd /mnt/user/appdata/eloverblick
cp .env.example .env
nano .env
```

Set:

```bash
ELOVERBLIK_TOKEN=your-refresh-token
POSTGRES_HOST=192.168.1.80
POSTGRES_PORT=5432
POSTGRES_USER=home
POSTGRES_PASSWORD=your-postgres-password
POSTGRES_DB=home
WEB_HOST=0.0.0.0
WEB_PORT=8080
```

`POSTGRES_HOST` must be an address **the container** can reach:

- Use the LAN IP of the machine that runs Postgres (for example `192.168.1.80`).
- Do **not** use `127.0.0.1` or `localhost`. Inside the container that is the container itself, not Unraid and not Postgres.
- If Postgres is another Unraid container, publish `5432` on the host (or put both on a shared custom network) and still use the Unraid LAN IP unless you attach this stack to the same Docker network and use the Postgres **container name**.

Do not commit `.env`. It is gitignored.

Postgres must accept connections from Docker. If the app logs `connection refused` or `password authentication failed`, check `listen_addresses`, `pg_hba.conf`, and that port `5432` is published.

## 4. Add the stack in Compose Manager

1. Docker tab → Compose → **Add New Stack**.
2. Name it `eloverblick`.
3. Open **Advanced** / **Advanced Options**.
4. Set **Indirect Path** to `/mnt/user/appdata/eloverblick` so the plugin uses the cloned repo as the compose project (build context included).
5. Save. Do not paste a second copy of the compose file into the USB plugin folder.

If the plugin has no Indirect Path field, skip the UI stack and start it from the terminal (step 5b).

Optional UI label: the compose file already sets `net.unraid.docker.webui` so Unraid can offer a WebUI link on port `8080`.

## 5. Start

### Compose Manager

On the Docker tab, for the `eloverblick` stack:

1. **Compose Up** (first run builds the image; that can take a minute).
2. Confirm the `eloverblick` container is running.
3. Open `http://<unraid-ip>:8080` (or the container WebUI link).

If Up does not rebuild after a later `git pull`, use the terminal command below.

### Terminal

```bash
cd /mnt/user/appdata/eloverblick
docker compose up -d --build
docker compose ps
docker compose logs -f web
```

The app listens on port **8080**. If that port is already used on Unraid, pick another `808x` host port on the left-hand side in `docker-compose.yml`:

```yaml
ports:
  - "8081:8080"
```

Then the UI is `http://<unraid-ip>:8081`. `WEB_PORT` stays `8080` (port inside the container).

## 6. Check it

- `http://<unraid-ip>:8080` shows ElOverblik and the selected address.
- `http://<unraid-ip>:8080/health` returns `ok`.
- On first start the app creates schema `eloverblick` and the hours/days/months/years tables in `POSTGRES_DB`.
- Open a date and use **Get data**. If that day is already stored, confirm before pulling again.

## Update

```bash
cd /mnt/user/appdata/eloverblick
git pull
docker compose up -d --build
```

`.env` is not in git, so pull will not overwrite the token or database password.

## Stop / remove

```bash
cd /mnt/user/appdata/eloverblick
docker compose down
```

That stops the web container only. It does not delete Postgres or the usage tables.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Build fails, missing Dockerfile | Indirect path is not the cloned repo, or files were not copied next to `docker-compose.yml`. |
| Container starts then dies | `docker compose logs web`. Missing `ELOVERBLIK_TOKEN` or Postgres settings in `.env`. |
| Cannot connect to Postgres | `POSTGRES_HOST` is `localhost`; Postgres not listening on the LAN IP; port `5432` not published; `pg_hba.conf` rejects the Docker/Unraid IP. |
| Port already allocated | Change the host port mapping (`"8081:8080"`). |
| Empty usage / API errors | Token, DataHub delay for yesterday, or no address selected (the app uses the single active address). |
| Compose Up does nothing after git pull | Rebuild: `docker compose up -d --build`. |

See [web.md](web.md) for the web app and table layout. See [script.md](script.md) for the Customer API client.