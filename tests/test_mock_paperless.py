import pytest
from fastapi import HTTPException

from apps.mock_paperless.main import authenticate
from core.config.settings import get_settings


def test_mock_uses_configured_paperless_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPERLESS_API_TOKEN", "configured-test-token")
    get_settings.cache_clear()
    try:
        authenticate("Token configured-test-token")
        with pytest.raises(HTTPException) as exc_info:
            authenticate("Token wrong-token")
        assert exc_info.value.status_code == 401
    finally:
        get_settings.cache_clear()
