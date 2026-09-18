"""Smoke-check the client: load ELOVERBLIK_TOKEN, ping the API, list meters."""

from script.client import CustomerApi
from script.settings import TOKEN_ENV_VAR


def main() -> None:
    api = CustomerApi.from_env()
    print(f"{TOKEN_ENV_VAR}: loaded")
    print(f"api alive: {api.is_alive()}")
    token = api.access_token()
    print(f"access token: obtained ({len(token)} chars)")
    points = api.metering_points()
    print(f"metering points: {len(points)}")
    for point in points:
        print(
            f"  {point.metering_point_id}  type={point.type_of_mp}  "
            f"relation={point.has_relation}  {point.address}"
        )


if __name__ == "__main__":
    main()
