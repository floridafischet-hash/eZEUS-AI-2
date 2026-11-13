# Sicherheitsprüfung vom 21. Oktober 2026

## Umfang

Die Prüfung umfasste Repository, Python-Abhängigkeiten, Anwendungsimage,
Secret-Hygiene, CI-Konfiguration, laufende Container und einen lesenden
Host-/OpenClaw-Überblick. Es wurden keine Firewall-, SSH-, Gateway- oder
Deployment-Einstellungen verändert.

## Ergebnis

- Bandit meldet keinen statischen Python-Sicherheitsbefund.
- Gitleaks meldet im Repository und dessen Historie kein Secret.
- Das neu gebaute Anwendungsimage enthält laut Trivy keine bekannte behebbare
  Schwachstelle der Schweregrade High oder Critical.
- `pip-audit` fand zunächst `PYSEC-2026-4320` in `certifi 2026.7.22`. Die
  Abhängigkeit wurde auf die behobene Version `2026.10.19` angehoben und beide
  Hash-Lockfiles wurden reproduzierbar neu erzeugt. Der anschließende Scan ist
  ohne Befund.
- Das Basisimage ist per Digest fixiert. Python-Pakete werden mit Hashprüfung
  installiert; GitHub Actions sind auf vollständige Commit-SHAs fixiert.
- Die Anwendungscontainer laufen als nicht privilegierter Benutzer. Die
  produktive Compose-API ist nur auf Loopback veröffentlicht; PostgreSQL,
  Redis und Ollama veröffentlichen keine Host-Ports.
- Das Helm-Deployment setzt ein schreibgeschütztes Root-Dateisystem,
  `RuntimeDefault`-Seccomp, `allowPrivilegeEscalation: false` und entfernt alle
  Linux-Capabilities.

## Offene Betriebsrisiken

### Mittel: Docker-Compose-Härtung

Die Compose-Anwendungscontainer laufen ohne Root und ohne privilegierten Modus,
verwenden aber derzeit weder `read_only: true` noch ein explizites
`cap_drop: [ALL]` oder `no-new-privileges`. Das ist schwächer als der Helm-
Security-Context. Vor einer Änderung müssen Schreibpfade und der vollständige
Compose-Smoke-Test geprüft werden.

### Mittel: Host-Angriffsfläche

Der Host besitzt mehrere Dienste auf Nicht-Loopback-Sockets. Ob alle davon
absichtlich über Reverse Proxy, Firewall oder privates Netz erreichbar sind,
konnte ohne privilegierten Firewall-Zugriff nicht bestätigt werden. SSH ist
aktiv. Automatische Sicherheitsupdates sind aktiv.

### Niedrig: OpenClaw-Betrieb

Das OpenClaw-Gateway selbst bindet ausschließlich an Loopback und der tiefe
Audit meldet keine kritischen Funde. Zwei Warnungen bleiben außerhalb dieses
Repositories bestehen: Der Hauptagent besitzt vollen Exec-Zugriff und mehrere
Plugin-Installationsangaben sind nicht auf exakte npm-Versionen fixiert.

### Nicht verifiziert

- Firewall-Regelwerk und externe Erreichbarkeit der Host-Ports
- Backup-Aktualität und erfolgreicher Restore-Test
- Verschlüsselung des Datenträgers
- Rotation produktiver Paperless-, Webhook- und Verschlüsselungs-Secrets

## Empfohlene nächste Schritte

1. Host-Ports und Firewall-Regeln mit administrativen Leserechten abgleichen.
2. Backup inklusive PostgreSQL und `CREDENTIAL_ENCRYPTION_KEY` testweise
   wiederherstellen.
3. Compose-Härtung in einer isolierten Testumgebung ergänzen und mit
   `make container-smoke` validieren.
4. OpenClaw-Exec für den Hauptagenten auf `ask` oder eine Allowlist begrenzen
   und Plugin-Installationsangaben auf exakte Versionen fixieren, sofern der
   aktuelle Betriebsablauf dies zulässt.
