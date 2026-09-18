# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.2] - 2026-09-18

### Added

- `example.md` with the Python commands to run the high-level client:
  1. set `ELOVERBLIK_TOKEN`
  2. initialize `CustomerApi`
  3. list and select the address to use
  4. total usage for a specific date
  5. 24 hours of usage for a specific date (`hours_for_day`)
  6. daily usage for a given month (`days_for_month`)
  7. monthly usage for a whole year (`months_for_year`)

## [0.0.1] - 2026-09-18

### Added

- Initial version of the project.
- OOP Python package in `script/` for the Customer API (token, metering points, yearly/monthly/daily/hourly time series).
- `script.md` documentation for the Python code.
- `addresses()` lists every installation on the API key with consumer name and `active` / `moved_out` status.
- `select_address()` stores the active address (or an explicit alternative) for later usage calls.
