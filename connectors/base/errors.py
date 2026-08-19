class ConnectorError(Exception):
    retryable = False


class AuthenticationError(ConnectorError):
    pass


class AuthorizationError(ConnectorError):
    pass


class NotFoundError(ConnectorError):
    pass


class RateLimitError(ConnectorError):
    retryable = True


class TimeoutError(ConnectorError):
    retryable = True


class ConnectionError(ConnectorError):
    retryable = True


class ConflictError(ConnectorError):
    pass


class ValidationError(ConnectorError):
    pass


class UnsupportedOperationError(ConnectorError):
    pass
