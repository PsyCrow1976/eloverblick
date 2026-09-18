"""Smoke-check: load token, list addresses, select the active one."""

from script.client import CustomerApi
from script.settings import TOKEN_ENV_VAR


def main() -> None:
    api = CustomerApi.from_env()
    print(f"{TOKEN_ENV_VAR}: loaded")
    print(f"api alive: {api.is_alive()}")
    token = api.access_token()
    print(f"access token: obtained ({len(token)} chars)")
    listed = api.addresses()
    print(f"addresses: {len(listed)}")
    for point in listed:
        name = point.name or "(no name)"
        print(
            f"  {point.metering_point_id}  {name}  "
            f"{point.address}  [{point.status}]"
        )
    selected = api.select_address()
    print(
        f"selected: {selected.metering_point_id}  {selected.name}  "
        f"{selected.address}  [{selected.status}]"
    )


if __name__ == "__main__":
    main()
