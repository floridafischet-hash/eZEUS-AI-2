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

Beim Speichern synchronisiert der Service alle aktiven, nicht systeminternen
Felder mit der API der zugeordneten Paperless-Instanz. Fehlende Felder werden
mit dem passenden Paperless-Datentyp erstellt; vorhandene Felder werden über
ihre ID oder ihren normalisierten Namen gebunden. Die dauerhafte externe ID
wird anschließend in `InstanceFieldConfig.external_field_id` gespeichert.
Beim Laden werden bislang unbekannte Custom Fields aus Paperless mandantenbezogen
als deaktivierte `InstanceFieldConfig` importiert. Ihr Aktivstatus ist eine
reine eZEUS-Einstellung; deaktivierte Einträge werden in Paperless weder
geändert noch entfernt.

`AdminUser` speichert individuelle Konten mit Scrypt-Passworthash, Rolle und
Aktivstatus. Das Bootstrap-Secret authentifiziert nur, solange noch kein
aktiver Administrator existiert. Damit bleibt die Ersteinrichtung möglich,
ohne im laufenden Betrieb ein gemeinsames Administrationskennwort zu verwenden.

Der Webhook normalisiert Paperless-Ereignisse und erzeugt ausschließlich
persistente Jobs. Celery transportiert Job-IDs über Redis; PostgreSQL bleibt die
Quelle für Status, Phasen, Ergebnisse und Auditdaten.

Der Worker führt folgende Phasen aus:

```text
LOAD_DOCUMENT -> DOWNLOAD_DOCUMENT (übersprungen) -> RUN_OCR (übersprungen)
-> WRITE_OCR (übersprungen) -> SELECT_TEMPLATE -> EXTRACT_FIELDS
-> VALIDATE_RESULTS -> RELOAD_METADATA -> WRITE_METADATA -> CLEANUP -> COMPLETE
```

Die Phasen `DOWNLOAD_DOCUMENT`, `RUN_OCR` und `WRITE_OCR` werden immer als
übersprungen markiert. Die Texterkennung übernimmt vollständig Paperless-ngx;
eZEUS liest den von Paperless bereitgestellten Text direkt aus den Metadaten.
Liefert Paperless keinen Text, schließt der Job mit `COMPLETED_WITH_WARNINGS` ab.

Der Orchestrator greift über `PaperlessConnector`, `TemplateService` und
Provider-Schnittstellen auf technische Komponenten zu. Provider schreiben
niemals direkt nach Paperless.

Ein partieller eindeutiger Datenbankindex verhindert mehrere aktive Jobs je
Dokument. `source_event_id` ist ebenfalls eindeutig. Vor jeder Schreiboperation
liest der Connector den aktuellen Paperless-Zustand erneut.
