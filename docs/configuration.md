# Konfiguration

Alle Werte werden über Umgebungsvariablen gelesen.

- `APP_ENV`: `development`, `test` oder `production`
- `APP_HOST`, `APP_PORT`: Bind-Adresse und Port des API-Containers
- `APP_LOG_LEVEL`: Log-Level für Uvicorn und Celery
- `FORWARDED_ALLOW_IPS`: von Uvicorn akzeptierte Proxy-Adressen; nur hinter
  einem abgeschirmten Cluster-Service auf `*` setzen
- `DATABASE_URL`: SQLAlchemy-Datenbank-URL; alternativ baut eZEUS sie aus
  `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_DATABASE` und
  `POSTGRES_PASSWORD`
- `REDIS_URL`: Celery-Broker und Result-Backend
- `PAPERLESS_BASE_URL`: Paperless-API-Basisadresse
- `PAPERLESS_API_TOKEN`: API-Token; in Produktion Pflicht
- `PAPERLESS_WEBHOOK_SECRET`: Webhook-Secret; in Produktion Pflicht
- `PROXY_AUTH_SECRET`: optionales internes Secret für einen vorgeschalteten,
  vertrauenswürdigen Authentifizierungs-Proxy
- `CREDENTIAL_ENCRYPTION_KEY`: URL-sicherer Fernet-Schlüssel zur Verschlüsselung
  gespeicherter Paperless-Zugangsdaten; in Produktion Pflicht
- `PUBLIC_WEBHOOK_BASE_URL`: optionale öffentliche Basisadresse für die auf der
  Verwaltungsseite angezeigten Webhook-URLs
- `PAPERLESS_VERIFY_TLS`: standardmäßig `true`
- `JOB_MAX_RETRIES`, `JOB_RETRY_DELAYS_SECONDS`: technische Retries
- `CELERY_CONCURRENCY`: Worker-Prozesse pro Compose-Container (Standard `2`;
  im Helm-Chart über `worker.args` gesetzt)
- `LOCAL_ONLY`: verhindert Cloud-Verarbeitung
- `OLLAMA_ENABLED`: aktiviert den lokalen LLM-Extraktionsprovider
- `OLLAMA_BASE_URL`: interne Ollama-API, standardmäßig
  `http://ollama:11434`
- `OLLAMA_MODEL`: lokales Modell, produktiv `qwen3:4b`
- `OLLAMA_TIMEOUT_SECONDS`: Zeitlimit pro Modellaufruf
- `OLLAMA_MAX_INPUT_CHARS`: maximale Textmenge pro Feldextraktion (längerer Paperless-Text wird gekürzt)
- `OLLAMA_MAX_RESPONSE_BYTES`: maximale gestreamte Ollama-Antwortgröße
- `OLLAMA_KEEP_ALIVE`: Vorhaltezeit des geladenen Modells
- `RATE_LIMIT_ENABLED`, `RATE_LIMIT_REQUESTS_PER_MINUTE`, `RATE_LIMIT_BURST`:
  anwendungsinterner Limiter pro Client
- `RATE_LIMIT_MAX_CLIENTS`: begrenzt die pro Prozess gespeicherten Client-
  Fenster (LRU), damit wechselnde Quell-IPs keinen unbeschränkten Speicher
  belegen
- `RATE_LIMIT_TRUST_PROXY_HEADERS`: Proxy-Header nur aktivieren, wenn der
  vorgeschaltete Proxy sie zuverlässig überschreibt
- `OUTBOUND_ALLOWED_HOSTS`: optionale feste, komma-separierte Host-Allowlist;
  sobald befüllt, gilt sie auch für verwaltete Paperless-Instanzen
- `OUTBOUND_PRIVATE_ALLOWED_HOSTS`: explizit erlaubte interne Hosts; Loopback,
  Link-Local und Metadatenadressen bleiben auch dann gesperrt
- `OUTBOUND_BLOCK_PRIVATE_NETWORKS`: standardmäßig `true`
- `PAPERLESS_MAX_DOWNLOAD_BYTES`: Streaming-Grenze pro Paperless-Antwort
- `PAPERLESS_MAX_TEXT_CHARS`: maximale Länge des übernommenen OCR-Texts
- `ALLOWED_DOCUMENT_MIME_TYPES`: akzeptierte Paperless-MIME-Typen
- `REGEX_HARD_TIMEOUT_SECONDS`: echte Unterbrechungsfrist pro Regex-Ausführung
- `OUTBOX_POLL_SECONDS`, `OUTBOX_CLAIM_TIMEOUT_SECONDS`, `OUTBOX_BATCH_SIZE`,
  `OUTBOX_MAX_BACKOFF_SECONDS`: Zustellparameter der transaktionalen Outbox

Secrets dürfen nicht in Images, Versionsverwaltung oder Logs abgelegt werden.
Im Produktionsmodus werden leere, mit `example-` beginnende und als
`change-me` markierte Anwendungs-Secrets abgelehnt.

## Mehrere Paperless-Instanzen

Die globalen `PAPERLESS_*`-Werte bleiben für den bisherigen Webhook
`/webhooks/paperless` erhalten. Zusätzliche Instanzen werden auf der
Verwaltungsseite `/admin/instances` angelegt. Jede Instanz besitzt:

- eine eindeutige Kennung,
- eine Paperless-Basis-URL,
- einen eigenen API-Token,
- ein eigenes Webhook-Secret,
- eine eigene Einstellung für die TLS-Prüfung,
- eine eigene Webhook-URL `/webhooks/paperless/<kennung>`.

API-Token und Webhook-Secret werden mit `CREDENTIAL_ENCRYPTION_KEY`
verschlüsselt gespeichert. Der Schlüssel darf nach dem Anlegen von Instanzen
nicht verloren gehen oder ungeplant geändert werden. Er muss zusammen mit der
Produktionskonfiguration gesichert werden. Ein Schlüsselwechsel erfordert eine
kontrollierte Neuverschlüsselung oder erneute Eingabe aller Zugangsdaten.
