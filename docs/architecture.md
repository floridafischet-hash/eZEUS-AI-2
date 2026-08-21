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
Aktivstatus. Das erste Konto wird außerhalb der HTTP-API mit dem interaktiven
Kommando `python -m scripts.create_admin_user <benutzername>` angelegt.

Der Webhook normalisiert Paperless-Ereignisse und speichert Job, initialen
Status und Queue-Outbox in derselben PostgreSQL-Transaktion. Ein eigener
Dispatcher claimt Outbox-Zeilen mit `FOR UPDATE SKIP LOCKED`, veröffentlicht
Job-IDs über Redis/Celery und wiederholt Fehler mit Backoff. PostgreSQL bleibt
die Quelle für Status, Phasen, Ergebnisse und Auditdaten. Doppelte
Celery-Zustellungen werden beim atomaren Job-Claim verworfen.

Der Worker führt folgende Phasen aus:

```text
LOAD_DOCUMENT -> READ_DOCUMENT_TEXT -> SELECT_TEMPLATE -> EXTRACT_FIELDS
-> VALIDATE_RESULTS -> RELOAD_METADATA -> WRITE_METADATA -> CLEANUP -> COMPLETE
```

Die Texterkennung übernimmt vollständig Paperless-ngx; eZEUS liest den von
Paperless bereitgestellten Text in `READ_DOCUMENT_TEXT` direkt aus den Metadaten.
Liefert Paperless keinen Text, schließt der Job mit `COMPLETED_WITH_WARNINGS` ab.

Der Orchestrator greift über `PaperlessConnector`, `TemplateService` und
Provider-Schnittstellen auf technische Komponenten zu. Provider schreiben
niemals direkt nach Paperless.

Ein partieller eindeutiger Datenbankindex verhindert mehrere aktive Jobs je
Dokument. `source_event_id` ist ebenfalls eindeutig. Vor jeder Schreiboperation
liest der Connector den aktuellen Paperless-Zustand erneut.
