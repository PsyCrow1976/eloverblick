# Examples

Run these from the repository root. Class details are in [script.md](script.md).

## 1. Set `ELOVERBLIK_TOKEN`

The refresh token from [eloverblik.dk](https://eloverblik.dk) must be in the environment before any Python code will work.

```bash
export ELOVERBLIK_TOKEN="your-refresh-token"
```

Check that it is set (this does not print the token):

```bash
python3 -c "import os; print('set' if os.environ.get('ELOVERBLIK_TOKEN') else 'missing')"
```

## 2. Initialize the class

```python
from script import CustomerApi

api = CustomerApi.from_env()
```

`from_env()` reads `ELOVERBLIK_TOKEN`. If the variable is missing, it raises `MissingTokenError`.

## 3. Set the address to use

List every address on the API key (name, street, active or moved out):

```python
for place in api.addresses():
    print(place.name, place.address, place.status)
```

Select the address that later usage calls will use. With no argument, the single **active** address is chosen. Pass a street name, metering point id, or consumer name to pick an alternative.

```python
api.select_address()
# api.select_address("Nordfeldvej")
# api.select_address("Frederikssundsvej")

print(api.selected_address.address, api.selected_address.status)
```

## 4. Example: total usage for a specific date

The date range is half-open: start day included, end day excluded. For **2026-09-16** only, request from that date to the next day.

```python
from datetime import date, timedelta

day = date(2026, 9, 16)
series = api.daily(day, day + timedelta(days=1))

usage = series[0]
print(api.selected_address.address)
print(day.isoformat(), usage.total(), usage.unit)
```

Example output:

```text
Nordfeldvej 21 2700 Brønshøj
2026-09-16 4.53 KWH
```

Change `day = date(2026, 9, 16)` to any other calendar date that DataHub has settled.
