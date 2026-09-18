# ElOverblik

Python script for the [ElOverblik Customer API](https://docs.eloverblik.dk/en/docs/api/customer). It fetches electricity consumption for private residents in Denmark at yearly, monthly, daily, and hourly resolution.

ElOverblik is Energinet’s portal for Danish electricity customers. The Customer API is meant for people who want their own meter data from DataHub — not for third-party companies acting on someone else’s behalf.

## What it does

- Authenticates as a private customer using a refresh token from [eloverblik.dk](https://eloverblik.dk)
- Lists metering points linked to that customer
- Pulls time series for those points with aggregation `Year`, `Month`, `Day`, or `Hour`

Official API docs: [Customer API](https://docs.eloverblik.dk/en/docs/api/customer)

## Requirements

- Python 3
- A personal refresh token from ElOverblik (Data → Access to data / API)

## Status

Initial version `0.0.1`. See [CHANGELOG.md](CHANGELOG.md).

## License

See the repository for license details.
