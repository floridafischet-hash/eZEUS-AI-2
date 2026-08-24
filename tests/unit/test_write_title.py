from unittest.mock import AsyncMock, patch

import pytest

from connectors.base.interface import ConnectorDocument
from connectors.paperless.connector import PaperlessConnector


def _connector(allow_title_overwrite: bool = False) -> PaperlessConnector:
    c = PaperlessConnector.__new__(PaperlessConnector)
    c.base_url = "http://paperless.test"
    c.token = "fake"
    c.verify_tls = False
    c.allow_title_overwrite = allow_title_overwrite
    c._settings = None
    return c


def _doc(title: str | None, filename: str | None = "invoice.pdf") -> ConnectorDocument:
    return ConnectorDocument(external_id="1", title=title, filename=filename)


@pytest.mark.asyncio
async def test_custom_title_is_not_overwritten() -> None:
    connector = _connector(allow_title_overwrite=False)
    with patch.object(connector, "get_document", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _doc(title="Manuell gesetzter Titel", filename="scan.pdf")
        result = await connector.write_title("1", "Neuer Titel")
    assert result is False


@pytest.mark.asyncio
async def test_empty_title_is_written() -> None:
    connector = _connector(allow_title_overwrite=False)
    with (
        patch.object(connector, "get_document", new_callable=AsyncMock) as mock_get,
        patch.object(connector, "_request", new_callable=AsyncMock) as mock_req,
    ):
        mock_get.return_value = _doc(title="", filename="scan.pdf")
        result = await connector.write_title("1", "Neuer Titel")
    assert result is True
    mock_req.assert_called_once()


@pytest.mark.asyncio
async def test_filename_matching_title_is_overwritten() -> None:
    connector = _connector(allow_title_overwrite=False)
    with (
        patch.object(connector, "get_document", new_callable=AsyncMock) as mock_get,
        patch.object(connector, "_request", new_callable=AsyncMock) as mock_req,
    ):
        mock_get.return_value = _doc(title="invoice", filename="invoice.pdf")
        result = await connector.write_title("1", "RE-2024-001")
    assert result is True
    mock_req.assert_called_once()


@pytest.mark.asyncio
async def test_overwrite_allowed_replaces_custom_title() -> None:
    connector = _connector(allow_title_overwrite=True)
    with (
        patch.object(connector, "get_document", new_callable=AsyncMock) as mock_get,
        patch.object(connector, "_request", new_callable=AsyncMock) as mock_req,
    ):
        mock_get.return_value = _doc(title="Alter Titel", filename="scan.pdf")
        result = await connector.write_title("1", "Neuer Titel")
    assert result is True
    mock_req.assert_called_once()


@pytest.mark.asyncio
async def test_identical_title_skips_write() -> None:
    connector = _connector(allow_title_overwrite=True)
    with patch.object(connector, "get_document", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _doc(title="Gleicher Titel")
        result = await connector.write_title("1", "Gleicher Titel")
    assert result is False


@pytest.mark.asyncio
async def test_none_title_is_written() -> None:
    connector = _connector(allow_title_overwrite=False)
    with (
        patch.object(connector, "get_document", new_callable=AsyncMock) as mock_get,
        patch.object(connector, "_request", new_callable=AsyncMock) as mock_req,
    ):
        mock_get.return_value = _doc(title=None, filename="scan.pdf")
        result = await connector.write_title("1", "Neuer Titel")
    assert result is True
    mock_req.assert_called_once()
