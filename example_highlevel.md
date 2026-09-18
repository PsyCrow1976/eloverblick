# High-level OOP examples

Run from the repository root. These calls return a single usage value (kWh) from `CustomerApi`.

Set the token first:

```bash
export ELOVERBLIK_TOKEN="your-refresh-token"
```

## Imports, timezone, and client

```python
from datetime import date
from zoneinfo import ZoneInfo

from script import CustomerApi

TIMEZONE = ZoneInfo("Europe/Copenhagen")

api = CustomerApi.from_env(timezone=TIMEZONE)
api.select_address()
```

Dates are calendar days in `Europe/Copenhagen`. `select_address()` stores the active meter on the client; later calls use that address.

## Usage for a single date

```python
print(api.usage_for_date(date(2026, 9, 16)))
```

```text
4.53
```

## Usage for a given month

```python
print(api.usage_for_month(2026, 9))
```

```text
74.6
```

## Usage for a whole year

```python
print(api.usage_for_year(2025))
```

```text
2001.88
```

## Full example

```python
from datetime import date
from zoneinfo import ZoneInfo

from script import CustomerApi

TIMEZONE = ZoneInfo("Europe/Copenhagen")

api = CustomerApi.from_env(timezone=TIMEZONE)
api.select_address()

day_kwh = api.usage_for_date(date(2026, 9, 16))
month_kwh = api.usage_for_month(2026, 9)
year_kwh = api.usage_for_year(2025)

print(day_kwh)
print(month_kwh)
print(year_kwh)
```
