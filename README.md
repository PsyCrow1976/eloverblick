# ElOverblik

Python script for the [ElOverblik Customer API](https://docs.eloverblik.dk/en/docs/api/customer). It fetches electricity consumption for private residents in Denmark at yearly, monthly, daily, and hourly resolution.

ElOverblik is Energinet’s portal for Danish electricity customers. The Customer API is meant for people who want their own meter data from DataHub — not for third-party companies acting on someone else’s behalf.

## What it does

- Authenticates as a private customer using a refresh token from [eloverblik.dk](https://eloverblik.dk)
- Lists addresses on the API key (consumer name, active or moved out)
- Selects the active address, or an alternative, for later usage calls
- Pulls time series for that address with aggregation `Year`, `Month`, `Day`, or `Hour`

Official API docs: [Customer API](https://docs.eloverblik.dk/en/docs/api/customer)

## Requirements

- Python 3
- `ELOVERBLIK_TOKEN` must be set in the environment before any Python code will run. This is the personal refresh token from ElOverblik (Data → Access to data / API).

```bash
export ELOVERBLIK_TOKEN="your-refresh-token"
```

Do not commit the token. Keep it in the environment (or a local `.env` that is gitignored). The scripts read `os.environ["ELOVERBLIK_TOKEN"]` and will fail if it is missing.

Python code lives in `script/`. Class and method documentation is in [script.md](script.md). Copy-paste examples are in [example.md](example.md).

```bash
python3 -m script
```

## Status

Version `0.0.2`. See [CHANGELOG.md](CHANGELOG.md).

## License

See the repository for license details.
