class ConnectorError(Exception):
    retryable = False


class AuthenticationError(ConnectorError):
    """Credentials were not accepted by the remote system."""


class AuthorizationError(ConnectorError):
    """Credentials lack permission for the requested operation."""


class NotFoundError(ConnectorError):
    """The requested remote resource does not exist."""


class RateLimitError(ConnectorError):
    retryable = True


class TimeoutError(ConnectorError):
    retryable = True


class ConnectionError(ConnectorError):
    retryable = True


class ConflictError(ConnectorError):
    """The remote state conflicts with the requested operation."""


class ValidationError(ConnectorError):
    """The request or remote document failed validation."""


class UnsupportedOperationError(ConnectorError):
    """The connector cannot perform the requested operation."""
