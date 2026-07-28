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

Der lokale Stack enthält einen Paperless-API-Mock und die PDF-Datei
`tests/fixtures/invoice.pdf` für manuelle End-to-End-Prüfungen. Der
automatisierte Integrationstest verwendet einen isolierten Connector und einen
OCR-Testprovider. Er prüft Templateauswahl, Extraktion, Validierung,
Persistierung, Audit und Schreibschutz ohne externe Dienste.
