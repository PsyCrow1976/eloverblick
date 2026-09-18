# Python code documentation

All Python code lives in the `script/` package. The design is object-oriented so new endpoints and aggregations can be added as methods on existing classes without rewriting callers.

Run commands from the repository root.

## Layout

| Path | Role |
| --- | --- |
| `script/settings.py` | `Settings` — reads `ELOVERBLIK_TOKEN` and the API base URL |
| `script/exceptions.py` | `ElOverblikError`, `MissingTokenError`, `ApiError`, `AddressSelectionError` |
| `script/models.py` | `Aggregation`, `MeteringPoint`, `TimeSeries`, `TimeSeriesPoint` |
| `script/client.py` | `CustomerApi` — HTTP client and public methods |
| `script/__init__.py` | Public imports |
| `script/__main__.py` | Smoke check: token, API alive, list metering points |

## Environment

`ELOVERBLIK_TOKEN` must be set before any Python code will work. It is the Customer API refresh token from [eloverblik.dk](https://eloverblik.dk).

```bash
export ELOVERBLIK_TOKEN="your-refresh-token"
```

`Settings.from_env()` and `CustomerApi.from_env()` both fail with `MissingTokenError` if the variable is missing or empty. Do not put the token in source files.

## How to call

```python
from datetime import date, timedelta
from script import CustomerApi, Aggregation

api = CustomerApi.from_env()

for place in api.addresses():
    print(place.name, place.address, place.status)

# Uses the single active address. Pass id/street/name for an alternative.
selected = api.select_address()
# selected = api.select_address("Frederikssundsvej")

today = date.today()
yesterday = today - timedelta(days=1)

hourly = api.hourly(yesterday, today)
daily = api.daily(yesterday, today)
monthly = api.monthly(date(today.year, 1, 1), today)
yearly = api.yearly(date(today.year, 1, 1), today)

series = api.time_series(yesterday, today, Aggregation.HOUR)
print(selected.address, series[0].total(), series[0].unit)
```

Smoke check:

```bash
python3 -m script
```

## Classes

### `Settings`

Holds `refresh_token` and `base_url`. Construct with `Settings.from_env()` so the token always comes from `ELOVERBLIK_TOKEN`.

### `CustomerApi`

Main entry point. One instance per session.

| Method | API |
| --- | --- |
| `from_env()` | Builds the client from `ELOVERBLIK_TOKEN` |
| `is_alive()` | `GET /isalive` |
| `access_token()` | `GET /token` (cached on the instance) |
| `metering_points(include_all=False)` | `GET /meteringpoints/meteringpoints` |
| `addresses(include_all=False)` | Same list, meant for name + `active` / `moved_out` |
| `select_address()` | Picks the single active address and stores it on the client |
| `select_address("street or id")` | Picks an alternative address (including moved-out) |
| `selected_address` | The address used by later usage calls |
| `time_series(date_from, date_to, aggregation)` | `POST /meterdata/gettimeseries/{from}/{to}/{aggregation}` |
| `hourly(date_from, date_to)` | aggregation `Hour` |
| `hours_for_day(day)` | 24 hourly readings for one calendar day |
| `daily(date_from, date_to)` | aggregation `Day` |
| `monthly(date_from, date_to)` | aggregation `Month` |
| `yearly(date_from, date_to)` | aggregation `Year` |

The refresh token is exchanged once for a data-access token (valid about 24 hours). Later calls reuse that access token on the same `CustomerApi` instance.

Date range is half-open: `date_from` inclusive, `date_to` exclusive, format `YYYY-MM-DD`. At most 10 metering point IDs per request.

Usage methods use `selected_address` when `metering_point_ids` is omitted. Call `select_address()` first.

`select_address()` with no argument requires exactly one active address. If none or several are active, pass the metering point id, street, or consumer name.

### `MeteringPoint`

One installation attached to the API key:

- `name` — consumer party name(s)
- `address` — street, number, postcode, city
- `status` — `active` or `moved_out`
- `is_active` / `is_moved_out`
- `metering_point_id`, plus `raw` for the original JSON

### `TimeSeries` / `TimeSeriesPoint`

Parsed meter data. `TimeSeries.points` is a flat list. `TimeSeries.total()` sums quantities. Original JSON is kept on `raw`.

### `Aggregation`

Enum: `Actual`, `Quarter`, `Hour`, `Day`, `Month`, `Year`.

## Adding code later

1. Put new modules in `script/`.
2. Add a method on `CustomerApi` for a new endpoint so callers stay on one object.
3. Put response shapes in `script/models.py` (or a new model module) instead of passing raw dicts around.
4. Raise `ApiError` (or a subclass in `exceptions.py`) for API failures.
5. Document the class and method in this file.

Example of a new endpoint:

```python
def charges(self, metering_point_ids):
    ids = _normalize_ids(metering_point_ids)
    payload = self._request(
        "POST",
        "/meteringpoints/meteringpoint/getcharges",
        body={"meteringPoints": {"meteringPoint": ids}},
    )
    return payload
```

## API notes

- Base URL: `https://api.eloverblik.dk/customerapi/api`
- Docs: https://docs.eloverblik.dk/en/docs/api/customer
- Time series are limited to the previous 5 years plus the current year, and at most 730 days per request.
- Token endpoint is limited to 2 calls per minute per IP. Do not refresh the data-access token more than once a day unless it failed.
