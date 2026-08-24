import pytest

from connectors.paperless.connector import PaperlessConnector


@pytest.mark.asyncio
async def test_connector_reuses_and_closes_lazy_http_client() -> None:
    connector = PaperlessConnector(
        base_url="https://paperless.example.test",
        api_token="test-token",
    )

    first = connector._client()
    second = connector._client()
    assert second is first
    assert first.is_closed is False

    await connector.close()
    assert first.is_closed is True

    replacement = connector._client()
    assert replacement is not first
    await connector.close()
    assert replacement.is_closed is True
