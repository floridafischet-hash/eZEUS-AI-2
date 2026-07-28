# Deployment

`docker compose up --build` erstellt API, PaddleOCR-Worker, PostgreSQL und Redis.
Der Entwicklungsstack enthält einen Paperless-API-Mock für reproduzierbare
End-to-End-Tests. Im Produktivbetrieb wird dieser entfernt und
`PAPERLESS_BASE_URL` auf eine aus dem Docker-Netz erreichbare Paperless-Instanz
gesetzt.

Die API führt vor dem Start Alembic-Migrationen aus. Die API läuft als nicht
privilegierter Benutzer. Der Worker startet zur Berechtigungsanpassung des
OCR-Modell-Volumes als Root und wechselt vor dem Celery-Start zum Benutzer
`ezeus`. Nur der über `APP_PORT` konfigurierte API-Port wird veröffentlicht.

Für Produktion müssen Images reproduzierbar gebaut, Paddle-Modelle vorab
gespeichert, TLS verwendet und Datenbank-/Redis-Netze eingeschränkt werden.
Backups müssen PostgreSQL-Daten und die verwendeten Templateversionen umfassen.
