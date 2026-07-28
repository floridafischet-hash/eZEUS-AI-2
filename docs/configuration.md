# Konfiguration

Alle Werte werden über Umgebungsvariablen gelesen.

- `APP_ENV`: `development`, `test` oder `production`
- `APP_HOST`, `APP_PORT`: Bind-Adresse und Port des API-Containers
- `APP_LOG_LEVEL`: Log-Level für Uvicorn und Celery
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
- `OLLAMA_ENABLED`: aktiviert den lokalen LLM-Extraktionsprovider
- `OLLAMA_BASE_URL`: interne Ollama-API, standardmäßig
  `http://ollama:11434`
- `OLLAMA_MODEL`: lokales Modell, produktiv `qwen3:4b`
- `OLLAMA_TIMEOUT_SECONDS`: Zeitlimit pro Modellaufruf
- `OLLAMA_MAX_INPUT_CHARS`: maximale OCR-Textmenge pro Feldextraktion
- `OLLAMA_KEEP_ALIVE`: Vorhaltezeit des geladenen Modells

Secrets dürfen nicht in Images, Versionsverwaltung oder Logs abgelegt werden.
Im Produktionsmodus werden leere, mit `example-` beginnende und als
`change-me` markierte Anwendungs-Secrets abgelehnt.
