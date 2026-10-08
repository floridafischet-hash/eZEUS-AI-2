from fastapi.testclient import TestClient

from apps.api.main import app


def test_help_page_contains_beginner_guide() -> None:
    response = TestClient(app).get("/help")

    assert response.status_code == 200
    assert "Benutzerhandbuch" in response.text
    assert "Schnellstart" in response.text
    assert "Paperless-Instanz anlegen" in response.text
    assert "Optionale Workflows und eigene Tag-Namen" in response.text
    assert "Günther" in response.text
    assert "Alte Tags" in response.text
    assert "Korrespondent, Titel und benutzerdefinierte Felder" in response.text
    assert "(noch nicht angelegt)" in response.text
    assert "Ein Fehler bei einem Wert stoppt die folgenden Versuche nicht" in response.text
    assert "Paperless-Webhook einrichten" in response.text
    assert "X-EZEUS-Webhook-Secret" in response.text
    assert "document_id" in response.text
    assert 'href="/help" aria-current="page"' in response.text


def test_navigation_links_to_help() -> None:
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert 'href="/help"' in response.text
