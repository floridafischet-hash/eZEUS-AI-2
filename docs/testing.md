# Tests

Die schnellen Tests verwenden keine externe Paperless-Instanz. Sie prüfen
Webhook-Sicherheit, Mandantentrennung, Outbox, SSRF-/Streaming-Grenzen,
Regex-Timeouts, Templates, Extraktion, Validierung und Schreibschutz.

```bash
python -m pip install --upgrade "pip==26.2.1" "setuptools==84.0.0" "wheel==0.48.0"
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation .
make format-check
make lint
make typecheck
make test
make security
```

Ein vollständiger Container-Test benötigt Docker:

```bash
make container-smoke
make smoke-down
make helm-check
```

`scripts/container_smoke_test.py` verwendet echte Container für PostgreSQL,
Redis, API, Outbox, Celery-Worker und Mock-Paperless. Er prüft den vollständigen
Webhook-Ablauf bis zu Titel und Custom Fields. CI führt zusätzlich Bandit,
`pip-audit`, Gitleaks, Trivy, SBOM-Erzeugung und 30-tägige
Artefaktaufbewahrung, Helm-Lint und kubeconform aus.
