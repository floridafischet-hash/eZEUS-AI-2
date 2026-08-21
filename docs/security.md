# Sicherheit

## Feldadministration und Mandantentrennung

Persönliche Administratorkonten werden mit Scrypt-gehashten Passwörtern
gespeichert. Die Anwendung verwendet über TLS die dedizierten Header
`X-EZEUS-Admin-User` und `X-EZEUS-Admin-Password`, damit die vorgelagerte
Nginx-Basic-Authentication ihren eigenen `Authorization`-Header unabhängig
verwenden kann. `admin` darf
Konfigurationen und Konten ändern; `viewer` darf Konfigurationen nur lesen und
Vorschauen ausführen. Das erste Administratorkonto wird einmalig über
`python -m scripts.create_admin_user <benutzername>` in einer administrativen
Shell angelegt; die HTTP-API besitzt keinen gemeinsamen Bootstrap-Schlüssel.

Bei vorgeschalteter HTTP-Basic-Authentifizierung kann der Reverse Proxy den
bereits geprüften Benutzernamen über `X-EZEUS-Proxy-User` weiterreichen. Die
Anwendung akzeptiert ihn nur zusammen mit dem internen
`X-EZEUS-Proxy-Secret`, dessen Wert `PROXY_AUTH_SECRET` entsprechen muss, und
nur wenn ein aktives Anwendungskonto mit demselben Namen existiert. Der Proxy
muss beide eingehenden Header stets überschreiben.

Der Mandant wird serverseitig aus `{instance_slug}` beziehungsweise bei der
Verarbeitung aus `Document.connector` bestimmt. Feldkonfigurations-Payloads
enthalten keine `instance_id`. Fremdschlüssel, eindeutige Constraints und
mandantenbezogene Abfragen bilden eine zweite Trennlinie unterhalb der API.
Alle Änderungen werden mit Akteur, Mandant, Zeitpunkt und Vorher-/Nachherwert
in `audit_entries` gespeichert.

Webhook-Secrets werden mit konstantem Zeitverhalten verglichen. Paperless-TLS
ist standardmäßig aktiv. Die API läuft nicht als Root. Vor jedem Schreiben wird
der Remotezustand erneut geladen.

## Umgesetzte technische Schutzmaßnahmen

- Der Helm-Ingress begrenzt Requests und Verbindungen; die Anwendung besitzt
  zusätzlich einen Burst-fähigen Limiter. Proxy-Header werden nur nach
  expliziter Aktivierung vertraut.
- Ausgehende Paperless- und Ollama-URLs werden gegen Host-Allowlisten geprüft.
  DNS-Ziele in privaten Netzen benötigen eine explizite Operator-Ausnahme;
  nur allowlist-geprüfte Kubernetes-Kurznamen dürfen private ClusterIPs nutzen.
  Loopback, Link-Local, Multicast und Cloud-Metadatenbereiche bleiben gesperrt.
  Pagination darf Origin, Schema oder Port nicht wechseln.
- Paperless-/Ollama-Antworten werden gestreamt und bereits beim Überschreiten
  der Grenze abgebrochen. MIME-Typ und Länge des übernommenen Paperless-OCR-
  Texts werden geprüft.
- Reguläre Ausdrücke laufen mit einer echten Engine-Frist; ein katastrophales
  Muster kann die Verarbeitung nicht unbegrenzt blockieren.
- Jobs und Queue-Ereignisse werden transaktional über PostgreSQL koordiniert.
  Der Outbox-Dispatcher stellt mit Claim-Timeout und Backoff zu; doppelte
  Celery-Zustellungen werden idempotent verworfen.
- Fehlermeldungen werden vor Persistierung und Anzeige strukturiert von
  Authorization-Headern, Tokens, Passwörtern und URL-Zugangsdaten bereinigt.
- Das eZEUS-Anwendungsimage läuft ohne Root, ohne Linux-Capabilities, mit
  `readOnlyRootFilesystem`, Seccomp und CPU-/Speicherlimits. Build-Werkzeuge
  werden aus dem finalen Image entfernt.
- CI prüft Hash-Lockfiles, Bandit, `pip-audit`, Gitleaks, Trivy (High/Critical),
  CycloneDX-SBOM mit 30-tägiger Artefaktaufbewahrung, Helm und
  Kubernetes-Manifeste sowie einen realen
  Container-Workflow.

## Verbleibende Betriebsgrenzen

eZEUS lädt und parst keine Dokumentbinärdateien. Dadurch liegt die Malware- und
PDF-Bomb-Prüfung der Originaldatei bei Paperless-ngx und dessen Importkette.
Betreiber müssen dort Scanner, Größen-/Seitenlimits und Quarantäne passend zur
eigenen Bedrohungslage konfigurieren. Vor dem Rollout bleiben außerdem ein
Lasttest mit der tatsächlichen Clustergröße, Restore-Test, Secret-Rotation und
eine installationsbezogene Security-Abnahme erforderlich.

## Repository- und Log-Hygiene

- `.env` und `.env.*` werden ignoriert; ausschließlich `.env.example` darf
  versioniert werden.
- `.env.example` enthält nur eindeutig markierte lokale Entwicklungswerte;
  der Produktionsmodus lehnt sie ab.
- Produktive Tokens und Passwörter müssen über eine lokale Secret-Datei oder
  einen Secret Manager injiziert werden.
- Das Dashboard gibt keine Dokumentinhalte, OCR-Texte oder Secrets aus.
  Angezeigte Phasen-Metadaten sind auf technische Ablaufdaten begrenzt;
  Fehlertexte werden vor Speicherung und Ausgabe redigiert.
- Konkrete Server-Adressen, Benutzernamen und installationsspezifische Pfade
  gehören nicht in Repository-Dokumentationen.
