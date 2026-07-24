# Konfiguration

Alle Werte werden über Umgebungsvariablen gelesen.

- `APP_ENV`: `development`, `test` oder `production`
- `APP_LOG_LEVEL`: Log-Level
- `DATABASE_URL`: SQLAlchemy-Datenbank-URL
- `REDIS_URL`: Celery-Broker und Result-Backend
- `PAPERLESS_BASE_URL`: Paperless-API-Basisadresse
- `PAPERLESS_API_TOKEN`: API-Token; in Produktion Pflicht
- `PAPERLESS_WEBHOOK_SECRET`: Webhook-Secret; in Produktion Pflicht
- `ADMIN_API_SECRET`: Secret für administrative API-Aufrufe; in Produktion Pflicht
- `PAPERLESS_VERIFY_TLS`: standardmäßig `true`
- `OCR_PROVIDER`: derzeit `paddleocr`
- `OCR_LANGUAGE`, `OCR_DEVICE`: OCR-Konfiguration
- `OCR_TIMEOUT_SECONDS`: Worker-Zeitlimit
- `MAX_DOCUMENT_BYTES`: maximale Downloadgröße
- `JOB_MAX_RETRIES`, `JOB_RETRY_DELAYS_SECONDS`: technische Retries
- `LOCAL_ONLY`: verhindert Cloud-Verarbeitung

Secrets dürfen nicht in Images, Versionsverwaltung oder Logs abgelegt werden.
