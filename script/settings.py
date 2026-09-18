"""Runtime settings. The refresh token is always read from the environment."""

from __future__ import annotations

import os

from script.exceptions import MissingTokenError

TOKEN_ENV_VAR = "ELOVERBLIK_TOKEN"
API_BASE_URL = "https://api.eloverblik.dk/customerapi/api"
API_VERSION = "1.0"


class Settings:
    """Holds the refresh token and API base URL used by CustomerApi."""

    def __init__(self, refresh_token: str, base_url: str = API_BASE_URL):
        token = (refresh_token or "").strip()
        if not token:
            raise MissingTokenError(
                f"{TOKEN_ENV_VAR} must be set before the Python code will work."
            )
        self.refresh_token = token
        self.base_url = base_url.rstrip("/")
        self.api_version = API_VERSION

    @classmethod
    def from_env(cls) -> Settings:
        """Load settings from ELOVERBLIK_TOKEN."""
        return cls(os.environ.get(TOKEN_ENV_VAR, ""))
