# Architektur

Der Webhook normalisiert Paperless-Ereignisse und erzeugt ausschließlich
persistente Jobs. Celery transportiert Job-IDs über Redis; PostgreSQL bleibt die
Quelle für Status, Phasen, Ergebnisse und Auditdaten.

Der Worker führt folgende Phasen aus:

```text
LOAD_DOCUMENT -> DOWNLOAD_DOCUMENT -> RUN_OCR -> WRITE_OCR
-> SELECT_TEMPLATE -> EXTRACT_FIELDS -> VALIDATE_RESULTS
-> RELOAD_METADATA -> WRITE_METADATA -> CLEANUP -> COMPLETE
```

Der Orchestrator greift über `PaperlessConnector`, `OCRAdapter`,
`TemplateService` und Provider-Schnittstellen auf technische Komponenten zu.
Provider schreiben niemals direkt nach Paperless.

Ein partieller eindeutiger Datenbankindex verhindert mehrere aktive Jobs je
Dokument. `source_event_id` ist ebenfalls eindeutig. Vor jeder Schreiboperation
liest der Connector den aktuellen Paperless-Zustand erneut.
