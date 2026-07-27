# Sicherheit

Webhook-Secrets werden mit konstantem Zeitverhalten verglichen. Paperless-TLS
ist standardmäßig aktiv. Downloads besitzen eine Größenbegrenzung und temporäre
Dateien liegen in automatisch bereinigten Verzeichnissen. Container laufen
nicht als Root. Vor jedem Schreiben wird der Remotezustand erneut geladen.

Vor einem Produktivbetrieb fehlen noch:

- rollenbasierte Autorisierung zusätzlich zur Secret-Authentifizierung für `/api/*`
- Rate Limiting am Reverse Proxy
- SSRF-Schutz durch eine administrativ feste Paperless-URL
- Malware-, PDF-Bomb- und Ressourcenlimits auf Betriebssystemebene
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
