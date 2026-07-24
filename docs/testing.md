# Tests

Die Tests verwenden keine externe Paperless-Instanz. Unit-Tests prüfen
OCR-Normalisierung, Webhook-Sicherheit, Templates, Extraktion und Validierung.

```bash
python -m pip install -e ".[dev]"
APP_ENV=test python -m pytest
ruff check .
mypy apps connectors core plugins webhooks
```

Ein vollständiger Container-Test benötigt Docker:

```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
```

Der lokale E2E-Stack enthält einen Paperless-API-Mock und die echte PDF-Datei
`tests/fixtures/invoice.pdf`. Der verifizierte Ablauf umfasst Webhook, Celery,
PaddleOCR, Template, Regex/Keyword, Validierung, PostgreSQL, Audit und
Paperless-Schreibschutz.
