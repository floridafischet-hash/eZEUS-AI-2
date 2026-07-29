# Changelog

Alle wesentlichen Änderungen an eZEUS-AI-2 werden in dieser Datei dokumentiert.

## Unveröffentlicht

- Mandantenbezogene Feldkonfiguration mit Standardvorlage, Custom-Feldern,
  Feldtypen, Pflichtstatus, Sortierung sowie OCR-/KI-Schaltern ergänzt.
- Geschützte Feldkonfigurations-API und Weboberfläche mit Vorschau ergänzt.
- Verarbeitungs-Pipeline an die dauerhaft gespeicherte Instanzkonfiguration
  gebunden.
- Konfigurationsänderungen um mandantenbezogene Auditdaten erweitert.

## 0.2.0 - 2026-07-27

### Hinzugefügt

- lokaler Ollama-Provider für strukturierte Feldextraktion
- Unterstützung für das lokale Modell `qwen3:4b`
- Betriebsdashboard am Startpfad `/`
- Reiter `Übersicht`, `Logs` und `API`
- bereinigte Log-API `GET /api/logs`
- automatische Aktualisierung des Log-Reiters
- Tests für Dashboard und Log-API

### Sicherheit

- `.env` aus der Versionsverwaltung entfernt
- `.env` und lokale Varianten in `.gitignore` aufgenommen
- Beispielkonfiguration auf eindeutig nicht produktive Standardwerte umgestellt
- Log-Ausgabe auf technische Metadaten ohne Dokumentinhalt und Secrets begrenzt

### Betrieb

- lokale KI bleibt ausschließlich über das private Container-Netz erreichbar
- produktive Reverse-Proxy-, Server- und Secret-Werte bleiben außerhalb des
  Repositorys
