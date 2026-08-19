# Deployment

`docker compose up --build` erstellt API, Worker, PostgreSQL und Redis.
Der Entwicklungsstack enthält einen Paperless-API-Mock für reproduzierbare
End-to-End-Tests. Im Produktivbetrieb wird dieser entfernt und
`PAPERLESS_BASE_URL` auf eine aus dem Docker-Netz erreichbare Paperless-Instanz
gesetzt. API und Worker verwenden dasselbe Image — kein gesondertes OCR-Image
ist nötig.

Die API führt vor dem Start Alembic-Migrationen aus. API und Worker laufen als
nicht privilegierter Benutzer. Nur der über `APP_PORT` konfigurierte API-Port
wird veröffentlicht.

Für Produktion müssen Images reproduzierbar gebaut, TLS verwendet und
Datenbank-/Redis-Netze eingeschränkt werden. Backups müssen PostgreSQL-Daten
und die verwendeten Templateversionen umfassen. Bei Verwendung der
Mehrinstanz-Verwaltung muss auch `CREDENTIAL_ENCRYPTION_KEY` gesichert werden.
Ohne diesen Schlüssel sind die verschlüsselten Paperless-API-Tokens und
Webhook-Secrets nicht wiederherstellbar.
