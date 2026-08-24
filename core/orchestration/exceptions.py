from connectors.base.errors import ConnectorError


class RetryableEmptyTextError(ConnectorError):
    """Paperless OCR text is not available yet and the job should retry."""

    retryable = True
