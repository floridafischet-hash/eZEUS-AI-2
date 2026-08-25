from fastapi.testclient import TestClient

from apps.api.main import app


def test_help_page_contains_beginner_guide() -> None:
    response = TestClient(app).get("/help")

    assert response.status_code == 200
    assert "Benutzerhandbuch" in response.text
    assert "Schnellstart" in response.text
    assert "Paperless-Instanz anlegen" in response.text
    assert 'href="/help" aria-current="page"' in response.text


def test_navigation_links_to_help() -> None:
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert 'href="/help"' in response.text
