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
    result = await connector.write_title(
        _doc(title="Manuell gesetzter Titel", filename="scan.pdf"), "Neuer Titel"
    )
    assert result is False


@pytest.mark.asyncio
async def test_empty_title_is_written() -> None:
    connector = _connector(allow_title_overwrite=False)
    with patch.object(connector, "_request", new_callable=AsyncMock) as mock_req:
        result = await connector.write_title(_doc(title="", filename="scan.pdf"), "Neuer Titel")
    assert result is True
    mock_req.assert_called_once()


@pytest.mark.asyncio
async def test_filename_matching_title_is_overwritten() -> None:
    connector = _connector(allow_title_overwrite=False)
    with patch.object(connector, "_request", new_callable=AsyncMock) as mock_req:
        result = await connector.write_title(
            _doc(title="invoice", filename="invoice.pdf"), "RE-2024-001"
        )
    assert result is True
    mock_req.assert_called_once()


@pytest.mark.asyncio
async def test_overwrite_allowed_replaces_custom_title() -> None:
    connector = _connector(allow_title_overwrite=True)
    with patch.object(connector, "_request", new_callable=AsyncMock) as mock_req:
        result = await connector.write_title(
            _doc(title="Alter Titel", filename="scan.pdf"), "Neuer Titel"
        )
    assert result is True
    mock_req.assert_called_once()


@pytest.mark.asyncio
async def test_identical_title_skips_write() -> None:
    connector = _connector(allow_title_overwrite=True)
    result = await connector.write_title(_doc(title="Gleicher Titel"), "Gleicher Titel")
    assert result is False


@pytest.mark.asyncio
async def test_none_title_is_written() -> None:
    connector = _connector(allow_title_overwrite=False)
    with patch.object(connector, "_request", new_callable=AsyncMock) as mock_req:
        result = await connector.write_title(_doc(title=None, filename="scan.pdf"), "Neuer Titel")
    assert result is True
    mock_req.assert_called_once()


@pytest.mark.asyncio
async def test_empty_fields_use_provided_document_snapshot() -> None:
    connector = _connector()
    document = ConnectorDocument(
        external_id="42",
        custom_fields={"10": None, "11": "manual-value"},
    )
    with patch.object(connector, "_request", new_callable=AsyncMock) as mock_req:
        changed = await connector.write_empty_fields(
            document,
            {"10": "extracted-value", "11": "must-not-overwrite"},
        )

    assert changed == {"10": "extracted-value"}
    mock_req.assert_awaited_once_with(
        "PATCH",
        "/api/documents/42/",
        json={
            "custom_fields": [
                {"field": 10, "value": "extracted-value"},
                {"field": 11, "value": "manual-value"},
            ]
        },
    )


@pytest.mark.asyncio
async def test_correspondent_write_uses_provided_document_snapshot() -> None:
    connector = _connector()
    document = ConnectorDocument(external_id="42", correspondent_id=None)
    with patch.object(connector, "_request", new_callable=AsyncMock) as mock_req:
        written = await connector.write_correspondent_if_empty(document, "7")

    assert written is True
    mock_req.assert_awaited_once_with("PATCH", "/api/documents/42/", json={"correspondent": 7})
