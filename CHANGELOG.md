# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.1] - 2026-09-18

### Added

- Initial version of the project.
- OOP Python package in `script/` for the Customer API (token, metering points, yearly/monthly/daily/hourly time series).
- `script.md` documentation for the Python code.
- `addresses()` lists every installation on the API key with consumer name and `active` / `moved_out` status.
- `select_address()` stores the active address (or an explicit alternative) for later usage calls.
- `example.md` with the commands to set `ELOVERBLIK_TOKEN`, initialize the client, select an address, and get one date's total usage.
