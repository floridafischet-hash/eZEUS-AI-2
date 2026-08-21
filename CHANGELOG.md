# Changelog

Alle wesentlichen Änderungen an eZEUS-AI-2 werden in dieser Datei dokumentiert.

## Unveröffentlicht

- Produktionsnahes Kubernetes-/Helm-Chart für API, Worker, Queue-Outbox,
  PostgreSQL, Redis, Ollama, Migrationen, Ingress/OIDC, HPA/PDB und
  NetworkPolicies ergänzt.
- Transaktionale PostgreSQL-Outbox mit wiederholbarer Celery-Zustellung und
  idempotentem Worker-Claim ergänzt.
- Host-Allowlisting, DNS-/Privatnetz- und Pagination-Origin-Schutz für
  Paperless-/Ollama-Aufrufe ergänzt.
- Harte Streaming-Grenzen, MIME-/OCR-Textgrenzen, echte Regex-Timeouts und
  strukturierte Fehlerredaktion ergänzt.
- Hash-basierte Runtime-/Development-Lockfiles sowie einen digest-gepinnten,
  CVE-geprüften Non-Root-Container-Build ergänzt.
- CI für Tests, Ruff, mypy, Bandit, `pip-audit`, Gitleaks, Trivy,
  CycloneDX-SBOM, Helm/kubeconform und vollständigen Compose-Smoke-Test ergänzt.
- Verwaltete Paperless-Workflows auf den sicheren Trigger „Dokument
  hinzugefügt“ beschränkt, damit eZEUS-Rückschreibungen keine Schleife auslösen.
- Proprietären/source-available Lizenzstatus ausdrücklich dokumentiert.
- Mandantenbezogene Feldkonfiguration mit Standardvorlage, Custom-Feldern,
  Feldtypen, Pflichtstatus, Sortierung sowie OCR-/KI-Schaltern ergänzt.
- Geschützte Feldkonfigurations-API und Weboberfläche mit Vorschau ergänzt.
- Verarbeitungs-Pipeline an die dauerhaft gespeicherte Instanzkonfiguration
  gebunden.
- Konfigurationsänderungen um mandantenbezogene Auditdaten erweitert.
- Individuelle Administratorkonten mit Scrypt-Passwörtern und den Rollen
  `admin` und `viewer` ergänzt; das gemeinsame Secret ist nur noch Bootstrap.
- Fehlende Paperless-Custom-Fields werden automatisch angelegt und verknüpft.
- Mandantenbezogene KI-Felder aktivieren Ollama ohne zusätzlichen globalen
  Extraktionsschalter.

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
