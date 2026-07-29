# Sicherheit

## Feldadministration und Mandantentrennung

Persönliche Administratorkonten werden mit Scrypt-gehashten Passwörtern
gespeichert und verwenden HTTP Basic ausschließlich über TLS. `admin` darf
Konfigurationen und Konten ändern; `viewer` darf Konfigurationen nur lesen und
Vorschauen ausführen. Das bestehende `ADMIN_API_SECRET` dient ausschließlich
zum Bootstrap des ersten aktiven Administrators und wird anschließend für
API-Zugriffe abgewiesen.

Der Mandant wird serverseitig aus `{instance_slug}` beziehungsweise bei der
Verarbeitung aus `Document.connector` bestimmt. Feldkonfigurations-Payloads
enthalten keine `instance_id`. Fremdschlüssel, eindeutige Constraints und
mandantenbezogene Abfragen bilden eine zweite Trennlinie unterhalb der API.
Alle Änderungen werden mit Akteur, Mandant, Zeitpunkt und Vorher-/Nachherwert
in `audit_entries` gespeichert.

Webhook-Secrets werden mit konstantem Zeitverhalten verglichen. Paperless-TLS
ist standardmäßig aktiv. Downloads besitzen eine Größenbegrenzung und temporäre
Dateien liegen in automatisch bereinigten Verzeichnissen. Externe Dateinamen
werden vor dem temporären Speichern auf den reinen Basisnamen reduziert. Die API
läuft nicht als Root. Der Worker wechselt nach der Berechtigungsanpassung des
OCR-Modell-Volumes zum Benutzer `ezeus`. Vor jedem Schreiben wird der
Remotezustand erneut geladen.

Vor einem Produktivbetrieb fehlen noch:

- Rate Limiting am Reverse Proxy
- SSRF-Schutz durch eine administrativ feste Paperless-URL
- Malware-, PDF-Bomb- und Ressourcenlimits auf Betriebssystemebene
- Streaming-Begrenzung von Downloads vor dem vollständigen Einlesen in den Speicher
- Dependency-, Container- und Secret-Scanning
- strukturierte Log-Redaktion und eine Security-Abnahme

## Repository- und Log-Hygiene

- `.env` und `.env.*` werden ignoriert; ausschließlich `.env.example` darf
  versioniert werden.
- `.env.example` enthält nur eindeutig markierte, nicht funktionsfähige
  Beispielwerte.
- Produktive Tokens und Passwörter müssen über eine lokale Secret-Datei oder
  einen Secret Manager injiziert werden.
- Das Dashboard gibt keine Dokumentinhalte, OCR-Texte, Secrets,
  Phase-Metadaten oder vollständigen Fehlertexte aus.
- Konkrete Server-Adressen, Benutzernamen und installationsspezifische Pfade
  gehören nicht in Repository-Dokumentationen.
