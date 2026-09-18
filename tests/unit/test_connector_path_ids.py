"""Paperless connector ids cannot escape their intended URL path."""

import pytest

from connectors.base.errors import ValidationError
from connectors.paperless.connector import PaperlessConnector, _path_id


@pytest.mark.parametrize("value", [1, "1", "42", " 7 "])
def test_path_id_accepts_positive_numeric_ids(value: object) -> None:
    assert _path_id(value) == str(value).strip()


@pytest.mark.parametrize(
    "value",
    ["../users/1", "1/../2", "1?x=1", "1#x", "0", "01", "-3", "", None, True, "a-1"],
)
def test_path_id_rejects_everything_else(value: object) -> None:
    with pytest.raises(ValidationError):
        _path_id(value)


@pytest.mark.asyncio
async def test_get_document_refuses_traversal_before_request(monkeypatch) -> None:
    connector = PaperlessConnector(
        base_url="https://paperless.example.test", api_token="test-token"
    )
    calls: list[str] = []

    async def fake_request(method: str, url: str, **_kwargs: object) -> None:
        calls.append(url)

    monkeypatch.setattr(connector, "_request", fake_request)
    with pytest.raises(ValidationError):
        await connector.get_document("../users/1")
    assert calls == []
    await connector.close()
