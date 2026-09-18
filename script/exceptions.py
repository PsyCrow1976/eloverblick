"""Errors raised by the ElOverblik Customer API client."""


class ElOverblikError(Exception):
    """Base error for all client failures."""


class MissingTokenError(ElOverblikError):
    """Raised when ELOVERBLIK_TOKEN is missing or empty."""


class ApiError(ElOverblikError):
    """Raised when the Customer API returns an error or unexpected payload."""

    def __init__(self, message, *, status_code=None, error_code=None, body=None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.body = body
