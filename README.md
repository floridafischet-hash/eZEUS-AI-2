# eZEUS-AI-2

eZEUS-AI-2 ist eine lokal bevorzugte, pluginfähige Dokumentenverarbeitung für
Paperless-ngx. Das Projekt verbindet Webhooks, persistente Jobs, PaddleOCR,
regelbasierte Extraktion, Validierung und konfliktarme Schreiboperationen.

## Reifegrad

Der Stand ist eine testbare minimale Verarbeitungspipeline, aber noch keine
freigegebene Produktionsversion. Insbesondere Referenzdatensynchronisation,
Authentifizierung der Administrations-API, Metriken und ein vollständiger
Security-/Lasttest fehlen noch.

## Voraussetzungen

- Docker Engine mit Docker Compose
- eine erreichbare Paperless-ngx-Instanz
- mindestens 8 GB RAM für den lokalen PaddleOCR-Worker empfohlen

## Schnellstart

```bash
cp .env.example .env
```

Sichere Werte für `POSTGRES_PASSWORD`, `PAPERLESS_API_TOKEN` und
`PAPERLESS_WEBHOOK_SECRET` eintragen. `PAPERLESS_BASE_URL` muss aus dem
Compose-Netz erreichbar sein.

```bash
docker compose up --build
```

Die API läuft anschließend auf `http://localhost:8080`. Beim API-Start wird
`alembic upgrade head` ausgeführt.

Der Compose-Stack enthält für reproduzierbare Entwicklungs- und E2E-Tests einen
lokalen Paperless-API-Mock. Für die Anbindung einer echten Instanz wird
`PAPERLESS_BASE_URL` auf deren aus dem Docker-Netz erreichbare Adresse gesetzt
und der Mock-Service aus einer produktiven Compose-Überlagerung entfernt.

## Paperless-Webhook

Paperless sendet einen `POST` an:

```text
http://<ezeus-host>:8080/webhooks/paperless
```

Header:

```text
X-EZEUS-Webhook-Secret: <PAPERLESS_WEBHOOK_SECRET>
```

Payload:

```json
{"document_id": 128, "event_id": "paperless-event-128"}
```

Ein neuer Job liefert HTTP 202, ein bereits bekanntes Event HTTP 200.

## Minimales Template anlegen

`POST /api/templates` akzeptiert mit dem Header
`X-EZEUS-Admin-Secret` ein validiertes JSON-Template:

```json
{
  "name": "Eingangsrechnung",
  "document_type_external_id": "7",
  "is_default": true,
  "config": {
    "fields": {
      "invoice_number": {
        "target_field_id": 14,
        "providers": [
          {"type": "regex", "patterns": ["(?i)rechnungsnummer[\\s:]+([A-Z0-9./_-]+)"]}
        ],
        "validators": [
          {"type": "required_pattern", "pattern": "^[A-Z0-9./_-]+$"}
        ]
      }
    }
  }
}
```

## Tests

```bash
python -m pip install -e ".[dev]"
APP_ENV=test python -m pytest
ruff check .
mypy apps connectors core plugins webhooks
```

## Wichtige Konfiguration

Siehe [.env.example](.env.example) und [docs/configuration.md](docs/configuration.md).
TLS-Prüfung ist standardmäßig aktiv. In `production` sind Paperless-Token und
Webhook-Secret Pflichtwerte.

## Bekannte Einschränkungen

- Version 1 unterstützt genau eine Paperless-Instanz.
- PaddleOCR-Modelle werden beim ersten Worker-Start gegebenenfalls geladen.
- PaddleOCR-Modelle werden im Volume `ocr_models` persistiert.
- Die Administrationsendpunkte verwenden ein gemeinsames Secret, aber noch keine Rollen.
- Paperless-Referenzdaten werden noch nicht lokal synchronisiert.
- Keyword-Extraktion arbeitet aktuell textuell; räumliche Nachbarschaft ist vorbereitet,
  aber noch nicht Teil der Auswahl.

Weitere Informationen stehen in `docs/`.
