# Architektur

## Mandanten- und Feldkonfiguration

`PaperlessInstance` ist die Mandantenwurzel. Die eindeutige `slug` wird aus
der Paperless-URL erzeugt und in Webhook-Pfaden sowie im Dokument-Connector
`paperless:<slug>` verwendet. `InstanceFieldConfig` gehört über `instance_id`
genau zu einer Instanz. API-Routen nehmen keine frei wählbare Mandanten-ID im
Request-Body entgegen, sondern lösen die Instanz aus dem Pfadsegment auf.

`FieldConfigurationService` stellt die Standardvorlage bereit, validiert und
speichert Änderungen, erzeugt Auditdaten und übersetzt die persistierte
Konfiguration in die vorhandene `TemplateConfig`. Der Orchestrator verwendet
für verwaltete Instanzen ausschließlich dieses Laufzeit-Template. Die
bisherigen dokumenttypbezogenen Templates bleiben für die Legacy-Konfiguration
erhalten.

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
