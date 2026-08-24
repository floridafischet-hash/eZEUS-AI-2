# eZEUS-AI-2

eZEUS-AI-2 ist eine lokale und mandantenfähige Verarbeitungspipeline für
Paperless-ngx. Die Anwendung reagiert auf Webhooks, liest den bereits von
Paperless erkannten Dokumenttext, extrahiert konfigurierte Werte und schreibt
geprüfte Ergebnisse zurück. Vorhandene manuelle Angaben werden dabei
geschützt.

Die OCR bleibt Aufgabe von Paperless-ngx. eZEUS-AI-2 bringt keine zweite
Texterkennung mit. Für einfache und gut strukturierte Dokumente reichen
reguläre Ausdrücke. Für schwierigere Fälle kann optional ein lokales
Ollama-Modell hinzugeschaltet werden. Ist Ollama deaktiviert oder nicht für ein
Feld vorgesehen, arbeitet die Verarbeitung nur mit den verbleibenden lokalen
Providern weiter.

Das Projekt ist für Docker Compose und Kubernetes ausgelegt. PostgreSQL hält
den dauerhaften Anwendungszustand, Redis dient als Celery-Broker und
Result-Backend. API, Worker, Outbox-Dispatcher und Job-Sweeper laufen als
getrennte Prozesse und können unabhängig betrieben und skaliert werden.

## Inhalt

- Funktionsumfang
- Architektur und Verarbeitung
- Paperless-Integration
- Installation mit Docker Compose
- Administrationsoberfläche und API
- Feldkonfiguration und Schreibschutz
- Warteschlangen, Wiederholungen und Sweeper
- Sicherheit und Zugangsschutz
- Konfiguration
- Monitoring und Logging
- Kubernetes und Helm
- Tests und Qualitätssicherung
- Betrieb und Fehleranalyse
- Projektstruktur

## Funktionsumfang

### Dokumentverarbeitung

- Annahme von Paperless-Webhooks über eine allgemeine oder eine
  instanzbezogene URL
- Schutz vor doppelten aktiven Jobs für dasselbe Dokument
- Dauerhafte Speicherung eines Jobs, bevor er an Celery übergeben wird
- Lesen des von Paperless bereitgestellten Dokumenttextes
- Retry mit Backoff, wenn Paperless seine OCR noch nicht abgeschlossen hat und
  der Text deshalb leer ist
- Auswahl der passenden Feldkonfiguration für die betroffene
  Paperless-Instanz
- Extraktion mit regulären Ausdrücken und optional Ollama
- Validierung und Normalisierung der gefundenen Werte
- Erneutes Laden der aktuellen Paperless-Metadaten unmittelbar vor dem
  Schreiben
- Geschütztes Schreiben von Titel, Korrespondent und benutzerdefinierten
  Feldern
- Vollständige Phasenhistorie und Audit-Einträge

### Mehrere Paperless-Instanzen

Paperless-Instanzen werden getrennt in der Datenbank verwaltet. Jede Instanz
besitzt unter anderem:

- einen eindeutigen Namen und Slug
- eine eigene Paperless-Basis-URL
- einen verschlüsselten API-Token
- ein verschlüsseltes Webhook-Secret
- eine eigene Feldkonfiguration
- eine eigene TLS-Einstellung
- einen eigenen Schreibschutz für Dokumenttitel

Für Webhooks wird bevorzugt die instanzbezogene URL verwendet:

```text
POST /webhooks/paperless/{instance-slug}
```

Der allgemeine Endpunkt bleibt für bestehende Installationen verfügbar:

```text
POST /webhooks/paperless
```

Bei diesem Endpunkt wird die Instanz nicht mehr durch einen linearen Scan aller
verschlüsselten Secrets gesucht. Stattdessen wird ein HMAC des eingehenden
Secrets berechnet und über eine indexierte Datenbankspalte gesucht. Nach dem
Treffer erfolgt weiterhin ein Vergleich in konstanter Zeit. Eine einzelne
beschädigte alte Credential-Zeile blockiert dabei keine anderen Instanzen.

Der allgemeine Endpunkt kann im Helm-Chart deaktiviert werden, sobald alle
Paperless-Instanzen ihre eigene URL verwenden.

### Administration

Die Administrationsfunktionen verwenden persönliche Benutzerkonten mit
Passworthash, Rolle und Aktivstatus. Es gibt keine Berechtigung allein durch
eingehende Proxy-User-Header. Ungeprüfte Header wie
`X-EZEUS-Proxy-User` und `X-EZEUS-Proxy-Secret` werden ignoriert.

Unterstützte Rollen:

- `admin` für Benutzerverwaltung und sicherheitsrelevante Änderungen
- `operator` für den laufenden Betrieb und die Konfiguration im erlaubten
  Umfang

Die Dashboard- und Admin-Endpunkte erwarten HTTP Basic Authentication oder die
entsprechenden Admin-Header. Der Zugriff auf `/api/logs` ist nicht öffentlich.

### Dashboard

Das integrierte Dashboard zeigt:

- den Zustand der angebundenen Dienste
- Jobs und deren aktuellen Status
- einzelne Verarbeitungsphasen
- redigierte Fehlermeldungen und Metadaten
- Filter nach Paperless-Instanz
- Suche nach Dokument, Dateiname, Job-ID oder Status
- cursorbasierte Pagination mit der Schaltfläche `Mehr laden`

Die erste Seite umfasst standardmäßig 50 Einträge. Weitere Seiten werden
nur bei Bedarf geladen. Die Abfrage nutzt einen zusammengesetzten Index auf
Erstellungszeitpunkt und Job-ID.

## Architektur und Verarbeitung

Ein Dokument durchläuft folgende Komponenten:

1. Paperless sendet einen Webhook an die FastAPI-Anwendung.
2. Die API validiert Instanz und Webhook-Secret.
3. Job und Outbox-Eintrag werden gemeinsam in PostgreSQL gespeichert.
4. Der Outbox-Dispatcher veröffentlicht den Auftrag an Redis.
5. Ein Celery-Worker reserviert und verarbeitet den Job.
6. Der Worker liest Dokument und Text aus Paperless.
7. Die konfigurierten Provider extrahieren die benötigten Werte.
8. Ergebnisse werden validiert und normalisiert.
9. Der Worker lädt das Dokument genau einmal erneut.
10. Derselbe aktuelle Snapshot wird an alle Schreiboperationen weitergegeben.
11. Erlaubte Änderungen werden an Paperless geschrieben.
12. Status, Phasen, Metriken und Audit-Daten werden gespeichert.

Die wichtigsten Laufzeitkomponenten sind:

- `apps.api` für Dashboard, Admin-API, Webhooks, Health und Metriken
- `apps.worker` für die eigentliche Dokumentverarbeitung
- `core.queue.outbox` für die transaktionale Übergabe an Celery
- `core.queue.sweeper` für liegengebliebene Jobs
- PostgreSQL für dauerhafte Daten
- Redis für Celery-Queues und kurzlebige Task-Ergebnisse
- optional Ollama für lokale KI-Extraktion

### Verarbeitungsphasen

Der Orchestrator protokolliert unter anderem folgende Phasen:

- `LOAD_DOCUMENT`
- `READ_DOCUMENT_TEXT`
- `SELECT_TEMPLATE`
- `EXTRACT_FIELDS`
- `VALIDATE_RESULTS`
- `RELOAD_METADATA`
- `WRITE_METADATA`
- `CLEANUP`
- `COMPLETE`

Start, Ende, Fehler und Laufzeit jeder Phase werden strukturiert erfasst.

## Paperless-Integration

### Voraussetzungen in Paperless

Für jede Instanz werden benötigt:

- die erreichbare Paperless-URL
- ein API-Token
- ein zufälliges Webhook-Secret
- benutzerdefinierte Felder, sofern extrahierte Werte dorthin geschrieben
  werden sollen

Paperless muss im Webhook mindestens die Dokument-ID übermitteln:

```json
{
  "document_id": 128,
  "event_id": "paperless-event-128"
}
```

Das Secret wird als Header gesendet:

```text
X-EZEUS-Webhook-Secret: <secret>
```

### Verbindung prüfen

Nach dem Anlegen einer Instanz kann deren Erreichbarkeit über die Admin-API
geprüft werden. Dabei werden URL, TLS-Konfiguration und API-Token verwendet.
Ausgehende Verbindungen unterliegen einer Host-Allowlist und Schutzregeln gegen
SSRF. Loopback- und Link-Local-Ziele sind nicht frei erreichbar.

### Wiederverwendeter HTTP-Client

Der Paperless-Connector verwendet pro Job einen wiederverwendeten
`httpx.AsyncClient`. Verbindungen und TLS-Sessions können dadurch innerhalb
eines Jobs wiederverwendet werden. Der Orchestrator schließt den Connector am
Jobende explizit, auch wenn die Verarbeitung mit einem Fehler endet.

## Installation mit Docker Compose

### Voraussetzungen

- Docker Engine
- Docker Compose v2
- eine erreichbare Paperless-ngx-Instanz
- mindestens Python 3.12 für lokale Entwicklungsarbeiten

Repository klonen:

```bash
git clone https://github.com/floridafischet-hash/eZEUS-AI-2.git
cd eZEUS-AI-2
cp .env.example .env
```

Vor einem produktiven Start müssen mindestens folgende Werte gesetzt werden:

```text
APP_ENV=production
POSTGRES_PASSWORD=<sicheres-passwort>
PAPERLESS_BASE_URL=https://paperless.example.org
PAPERLESS_API_TOKEN=<paperless-token>
PAPERLESS_WEBHOOK_SECRET=<zufälliges-webhook-secret>
CREDENTIAL_ENCRYPTION_KEYS=<fernet-keyring>
WEBHOOK_LOOKUP_HMAC_KEY=<mindestens-32-byte-zufallswert>
```

Einen Fernet-Key erzeugen:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Container bauen und starten:

```bash
docker compose up -d --build
```

Status prüfen:

```bash
docker compose ps
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/ready
```

Das Compose-Setup enthält eine Mock-Paperless-Anwendung für Entwicklung und
automatisierte Integrationstests. Für einen produktiven Betrieb muss
`PAPERLESS_BASE_URL` auf die reale Installation zeigen.

### Ersten Administrator anlegen

```bash
docker compose exec api python scripts/create_admin_user.py admin
```

Das Passwort wird interaktiv abgefragt und nicht als Kommandozeilenargument
gespeichert. Für kontrollierte Automatisierung kann es aus einer
Umgebungsvariable gelesen werden:

```bash
docker compose exec -e ADMIN_BOOTSTRAP_PASSWORD api \
  python scripts/create_admin_user.py admin \
  --password-env ADMIN_BOOTSTRAP_PASSWORD \
  --if-not-exists
```

### Migrationen

Die Compose-Dienste starten die Migration vor der Anwendung. PostgreSQL
Advisory Locks serialisieren parallele Migrationsversuche. Die Migrationen sind
auch auf einer frischen Datenbank wiederholbar.

Manueller Aufruf:

```bash
docker compose exec api python -m core.db.migrate
```

## Feldkonfiguration und Schreibschutz

Felder werden pro Paperless-Instanz konfiguriert. Eine Konfiguration enthält
unter anderem:

- Feldschlüssel und sichtbare Bezeichnung
- Datentyp
- Sortierreihenfolge
- Aktivstatus
- Pflichtfeldstatus
- externe Paperless-Feld-ID
- reguläre Ausdrücke
- optionale Extraktionsanweisungen für Ollama
- Auswahl, ob KI für dieses Feld aktiviert ist

### Regex und Ollama

Regex ist der Standardprovider. Ist für ein Feld zusätzlich KI aktiviert und
`OLLAMA_ENABLED=true`, wird Ollama nach Regex ausgeführt. Ist Ollama global
deaktiviert, wird der Ollama-Provider gar nicht erst in die Providerliste
aufgenommen. Ein AI-aktiviertes Feld kann dadurch sauber auf Regex
zurückfallen, ohne einen Verbindungsfehler zu erzeugen.

### Geschützte Schreiboperationen

Benutzerdefinierte Felder und Korrespondenten werden nur geschrieben, wenn das
Ziel noch leer ist. Dokumenttitel werden nur geändert, wenn:

- der aktuelle Titel leer ist oder
- der aktuelle Titel dem ursprünglichen Dateinamen ohne Erweiterung entspricht

Ein davon abweichender, manuell gesetzter Titel bleibt erhalten. Pro Instanz
kann mit `allow_title_overwrite` ein bewusstes Überschreiben aktiviert werden.
Diese Option ist standardmäßig ausgeschaltet.

## Warteschlangen, Wiederholungen und Sweeper

### Transactional Outbox

Job und Queue-Ereignis werden in derselben Datenbanktransaktion angelegt. Erst
danach übergibt der Outbox-Dispatcher den Auftrag an Redis. Ein bestätigter
Webhook geht deshalb nicht verloren, nur weil Redis kurzzeitig nicht erreichbar
ist.

Fehlgeschlagene Veröffentlichungen werden mit exponentiellem Backoff erneut
versucht. Fehlermeldungen werden vor der Speicherung redigiert.

### Prioritäten und Mandantenfairness

Celery verwendet die Queues `high`, `normal` und `low`. Beim Enqueue wird die
Zahl aktiver Jobs der betroffenen Instanz geprüft. Überschreitet sie
`MAX_CONCURRENT_JOBS_PER_INSTANCE`, werden weitere Jobs dieser Instanz in die
Low-Priority-Queue gelegt. Ein großer Rückstau einer Instanz soll dadurch
andere Instanzen nicht vollständig blockieren.

### Retry bei noch leerem Paperless-Text

Ein leerer Dokumenttext wird nicht als erfolgreich verarbeitet. Der
Orchestrator wirft eine retryfähige Ausnahme, weil Paperless seine eigene OCR
möglicherweise noch nicht beendet hat. Celery plant den Job mit Backoff erneut
ein.

### Job-Sweeper

Der Sweeper sucht regelmäßig nach Jobs in nicht terminalen Zuständen:

- `RECEIVED`
- `QUEUED`
- `RUNNING`
- `RETRY_WAITING`

Als Heartbeat dient `updated_at`, das bei Phasenfortschritten aktualisiert wird.
Ist ein Job länger als der konfigurierte Schwellwert unverändert, wird er
erneut über die Outbox eingeplant oder nach ausgeschopften Retries auf
`FAILED` gesetzt. Damit kann die Unique Constraint für aktive Dokumentjobs
nicht dauerhaft durch einen abgestürzten Worker blockiert werden.

Auch die manuelle Retry-Funktion akzeptiert hängende Jobs in aktiven
Zuständen.

### Celery-Grenzen

Der Soft-Limit orientiert sich an der maximalen Laufzeit einer
Ollama-Verarbeitung. Der Hard-Limit ist davon getrennt konfiguriert:

```text
CELERY_TASK_TIME_LIMIT_SECONDS=420
```

Der Hard-Limit muss größer als Soft-Limit plus Sicherheitsabstand sein.
Task-Ergebnisse erhalten eine konfigurierbare Ablaufzeit:

```text
CELERY_RESULT_EXPIRES_SECONDS=3600
```

Das interne Redis verwendet eine begrenzte Speichermenge und `noeviction`,
damit Broker-Nachrichten nicht unbemerkt verdrängt werden. Die TTL verhindert,
dass Task-Ergebnisse dauerhaft Speicher belegen.

## Sicherheit und Zugangsschutz

### Zugang zur Administration

Admin-Routen verwenden `require_admin_user`. Passwörter werden mit scrypt und
einem individuellen Salt gehasht. Deaktivierte Benutzer können sich nicht
anmelden. Rollenprüfungen verhindern, dass Operatoren Funktionen ausführen,
die ausschließlich Administratoren vorbehalten sind.

Bei einem Ingress mit oauth2-proxy führt ingress-nginx den OIDC-Auth-Request
aus. Ungeprüfte eingehende eZEUS-Proxy-Header werden vor dem Forwarding
entfernt. Die Anwendung selbst vertraut diesen Headern nicht als Anmeldung.

### Webhook-Schutz

- eigenes Secret je Paperless-Instanz
- HMAC-basierter und indexierter Lookup
- Constant-Time-Vergleich nach dem Lookup
- getrennte Ingress-Regeln ohne Browser-OIDC
- eigene Request-Rate-Limits
- konfigurierbare maximale Body-Größe
- optionale IP-Allowlist
- optional deaktivierbarer allgemeiner Webhook-Endpunkt

### Verschlüsselung und Rotation

API-Token und Webhook-Secrets werden mit Fernet verschlüsselt gespeichert.
`CREDENTIAL_ENCRYPTION_KEYS` enthält eine geordnete, kommagetrennte Key-Liste.
Der erste Key ist aktiv für neue Verschlüsselungen, alle Keys können alte
Werte entschlüsseln. Die alte Variable `CREDENTIAL_ENCRYPTION_KEY` bleibt für
Installationen mit nur einem Key kompatibel.

Der Rotationsablauf ist:

1. Backup der Datenbank und aller bisher verwendeten Keys erstellen.
2. Neuen Key an die erste Stelle von `CREDENTIAL_ENCRYPTION_KEYS` setzen.
3. Alte Keys dahinter belassen.
4. Anwendung neu starten und Entschlüsselung prüfen.
5. Verschlüsselte Spalten neu verschlüsseln:

```bash
docker compose exec api python scripts/rotate_credentials.py
```

6. Erst nach erfolgreicher Prüfung alte Keys entfernen.

Ein verlorener letzter Entschlüsselungs-Key kann nicht aus der Datenbank
wiederhergestellt werden. Key-Backups gehören deshalb zwingend zum
Backup-Konzept.

### Weitere Schutzmaßnahmen

- Container läuft als Non-Root-Benutzer
- Kubernetes SecurityContext ohne zusätzliche Linux-Capabilities
- schreibgeschütztes Root-Dateisystem im Helm-Deployment
- Secrets werden nicht in Logs ausgegeben
- sensible Fehlermeldungen und Metadaten werden redigiert
- Größenlimits für Paperless-Downloads, Texte und Ollama-Antworten
- Timeout für reguläre Ausdrücke
- ausgehende Host-Allowlist
- TLS-Verifikation für Paperless
- Rate-Limits in Anwendung und Ingress
- produktiver Start wird bei Beispiel-Secrets oder SQLite verweigert

## Wichtige Konfiguration

Die vollständige Referenz steht in `docs/configuration.md` und in
`.env.example`. Die folgenden Variablen sind für den aktuellen Betrieb
besonders relevant.

### Anwendung und Dienste

| Variable | Zweck |
| --- | --- |
| `APP_ENV` | `development` oder `production` |
| `APP_HOST`, `APP_PORT` | Bind-Adresse und Port der API |
| `DATABASE_URL` | Externe Datenbankverbindung, falls gesetzt |
| `POSTGRES_HOST`, `POSTGRES_PORT` | Einzelparameter für PostgreSQL |
| `POSTGRES_USER`, `POSTGRES_PASSWORD` | Datenbankzugang |
| `POSTGRES_DATABASE` | Datenbankname |
| `REDIS_URL` | Celery-Broker und Result-Backend |
| `PAPERLESS_BASE_URL` | Standard-Paperless-URL |
| `PAPERLESS_API_TOKEN` | Standard-Paperless-Token |
| `PAPERLESS_WEBHOOK_SECRET` | Legacy-Webhook-Secret |

### Datenbankpool

| Variable | Standard | Zweck |
| --- | --- | --- |
| `DB_POOL_SIZE` | `5` | dauerhafte Verbindungen pro Prozess |
| `DB_MAX_OVERFLOW` | `5` | zusätzliche kurzzeitige Verbindungen |
| `DB_POOL_TIMEOUT_SECONDS` | `30` | Wartezeit auf eine freie Verbindung |

Bei der Dimensionierung zählen alle API-, Worker-, Outbox- und
Sweeper-Prozesse. Die Summe aus Pool und Overflow aller Replikate muss mit
ausreichender Reserve unter `max_connections` von PostgreSQL bleiben.

### Ollama

| Variable | Zweck |
| --- | --- |
| `OLLAMA_ENABLED` | lokale KI-Verarbeitung aktivieren |
| `OLLAMA_BASE_URL` | Ollama-Dienst |
| `OLLAMA_MODEL` | verwendetes Modell, zum Beispiel `qwen3:4b` |
| `OLLAMA_TIMEOUT_SECONDS` | maximale Wartezeit |
| `OLLAMA_MAX_INPUT_CHARS` | maximale Eingabelänge |
| `OLLAMA_MAX_RESPONSE_BYTES` | maximale Antwortgröße |

### Queue und Wiederherstellung

| Variable | Zweck |
| --- | --- |
| `JOB_MAX_RETRIES` | maximale automatische Wiederholungen |
| `JOB_RETRY_DELAYS_SECONDS` | Backoff-Folge |
| `MAX_CONCURRENT_JOBS_PER_INSTANCE` | Grenze vor Low-Priority-Routing |
| `CELERY_TASK_TIME_LIMIT_SECONDS` | harter Task-Limit |
| `CELERY_RESULT_EXPIRES_SECONDS` | TTL für Task-Ergebnisse |
| `SWEEPER_INTERVAL_SECONDS` | Sweeper-Intervall |
| `SWEEPER_STALE_THRESHOLD_SECONDS` | Schwellwert für hängende Jobs |
| `OUTBOX_POLL_SECONDS` | Polling-Intervall des Dispatchers |
| `OUTBOX_CLAIM_TIMEOUT_SECONDS` | Freigabe verwaister Claims |
| `OUTBOX_BATCH_SIZE` | maximale Events pro Lauf |

## Monitoring und Logging

### Health-Endpunkte

```text
GET /health
GET /ready
GET /metrics
```

`/health` zeigt, dass der API-Prozess lebt. `/ready` prüft PostgreSQL, Redis,
Paperless und bei Bedarf Ollama. Die Prüfung hat einen harten Timeout, damit
eine hängende Datenbankverbindung die Kubernetes-Readiness nicht unbegrenzt
blockiert.

### Prometheus-Metriken

Der Prometheus-Export enthält mindestens:

- Job-Counter nach Status und Instanz-Slug
- Histogramme für Phasenlaufzeiten
- Webhook-Counter nach Statuscode und Instanz
- Outbox-Counter für erfolgreiche und fehlgeschlagene Publikationen
- aktuelle Celery-Queue-Tiefe für `high`, `normal` und `low`

Das Helm-Chart setzt Scrape-Annotationen und kann optional einen
`ServiceMonitor` für den Prometheus Operator erzeugen.

### Strukturierte Logs

Die Anwendung schreibt JSON-Zeilen nach stdout. Je nach Kontext enthalten sie:

- Zeitstempel
- Log-Level
- Logger
- Nachricht
- `job_id`
- `instance_slug`
- `phase`
- `worker_id`
- `document_id`
- redigierte Exception-Informationen

Der Orchestrator loggt jeden Phasenstart und jedes Phasenende. Worker loggen
Task-Annahme, Claim, Erfolg, Retry und Fehler. Connector- und Webhook-Fehler
werden mit ihrem technischen Grund und ohne Klartext-Secrets protokolliert.

## Kubernetes und Helm

Das Chart liegt unter `deploy/helm/ezeus-ai-2` und enthält:

- API Deployment und Service
- Worker Deployment
- Outbox Deployment
- Sweeper Deployment
- Migrations-Job und Migrations-Init-Container
- PostgreSQL StatefulSet und PVC
- Redis StatefulSet und PVC
- optionales Ollama StatefulSet und PVC
- ConfigMap und Secret-Anbindung
- Ingress für Browser, Health, oauth2-proxy und Webhooks
- optionalen oauth2-proxy
- NetworkPolicies
- Resource Requests und Limits
- Liveness- und Readiness-Probes
- HorizontalPodAutoscaler für API und Worker
- PodDisruptionBudgets
- optionalen ServiceMonitor

### Image bauen

```bash
docker build -t registry.example.org/ezeus-ai-2:0.2.0 .
docker push registry.example.org/ezeus-ai-2:0.2.0
```

### Werte vorbereiten

```bash
cp deploy/helm/ezeus-ai-2/values-production.example.yaml values-production.yaml
```

In der Datei müssen mindestens Image, Ingress-Host, TLS, Paperless-Ziel,
NetworkPolicy-CIDRs und die Referenz auf ein bestehendes Secret angepasst
werden.

### Secret anlegen

Für produktive Systeme sollten External Secrets, Sealed Secrets oder eine
vergleichbare Secret-Verwaltung verwendet werden. Ein direktes Kubernetes
Secret kann für eine kontrollierte Installation so angelegt werden:

```bash
kubectl create namespace ezeus
kubectl -n ezeus create secret generic ezeus-secrets \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --from-literal=PAPERLESS_API_TOKEN="$PAPERLESS_API_TOKEN" \
  --from-literal=PAPERLESS_WEBHOOK_SECRET="$PAPERLESS_WEBHOOK_SECRET" \
  --from-literal=CREDENTIAL_ENCRYPTION_KEYS="$CREDENTIAL_ENCRYPTION_KEYS" \
  --from-literal=WEBHOOK_LOOKUP_HMAC_KEY="$WEBHOOK_LOOKUP_HMAC_KEY"
```

### Installation

```bash
helm upgrade --install ezeus deploy/helm/ezeus-ai-2 \
  --namespace ezeus \
  --create-namespace \
  --values values-production.yaml \
  --set existingSecret=ezeus-secrets \
  --set image.repository=registry.example.org/ezeus-ai-2 \
  --set image.tag=0.2.0 \
  --wait \
  --timeout 10m
```

Rollout prüfen:

```bash
kubectl -n ezeus rollout status deployment/ezeus-ezeus-ai-2-api
kubectl -n ezeus rollout status deployment/ezeus-ezeus-ai-2-worker
kubectl -n ezeus get pods,services,ingress
```

### NetworkPolicy

Die API akzeptiert Verkehr vom oauth2-proxy derselben Installation. Bei
aktiviertem Ingress werden zusätzlich nur Controller-Pods zugelassen, deren
Namespace und Labels zu `allowedIngressNamespaces` und
`ingressControllerPodLabels` passen. Damit werden nicht pauschal alle Pods
eines Ingress-Namespace freigeschaltet.

Externe Paperless-, PostgreSQL-, Redis- oder Ollama-Ziele müssen über genaue
`egressCidrs` erreichbar gemacht werden. Uneingeschränkte CIDRs wie
`0.0.0.0/0` werden vom Values-Schema abgelehnt.

## Tests und Qualitätssicherung

Lokale Entwicklungsumgebung:

```bash
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-dev.lock
.venv/bin/pip install --no-deps --no-build-isolation .
```

Vollständige Test-Suite:

```bash
make test
```

Weitere Qualitätsprüfungen:

```bash
make lint
make format-check
make typecheck
make security
make helm-check
```

Der Container-Smoke-Test baut den kompletten Stack mit einer frischen
PostgreSQL-Datenbank, startet API, Worker, Outbox, Redis und Mock-Paperless und
verarbeitet ein Dokument bis zum Rückschreiben:

```bash
make container-smoke
make smoke-down
```

Die GitHub-CI führt dieselben Qualitäts-, Helm- und Containerprüfungen aus.
Zusätzlich werden Repository-Secrets mit Gitleaks und das Container-Image mit
Trivy geprüft. Für jedes Image wird ein CycloneDX-SBOM erzeugt.

## Betrieb und Fehleranalyse

### Job bleibt aktiv

Zuerst Worker und Sweeper prüfen:

```bash
docker compose logs worker
docker compose logs outbox
docker compose logs api
```

In Kubernetes:

```bash
kubectl -n ezeus logs deployment/ezeus-ezeus-ai-2-worker
kubectl -n ezeus logs deployment/ezeus-ezeus-ai-2-sweeper
kubectl -n ezeus logs deployment/ezeus-ezeus-ai-2-outbox
```

Ein wirklich verwaister Job wird nach dem konfigurierten Schwellwert vom
Sweeper behandelt. Ein manueller Retry ist über die Admin-API möglich.

### Paperless-Text ist leer

Das ist meistens ein Race zwischen Paperless-OCR und Webhook. Der Job wird
nicht erfolgreich mit leeren Ergebnissen beendet, sondern mit Backoff erneut
eingeplant. Wiederholte Fehler deuten auf fehlenden OCR-Text oder ein Problem in
Paperless hin.

### Ollama ist nicht erreichbar

Wenn Ollama nicht verwendet werden soll, muss `OLLAMA_ENABLED=false` gesetzt
werden. Dann werden AI-Provider übersprungen und Regex bleibt aktiv. Wenn
Ollama verwendet werden soll, prüfen:

```bash
curl http://ollama:11434/api/tags
```

### Readiness meldet 503

Die Antwort nennt die fehlgeschlagene Abhängigkeit. Typische Ursachen sind:

- PostgreSQL nicht erreichbar oder Pool erschöpft
- Redis nicht erreichbar
- Paperless-URL oder Token falsch
- Ollama aktiviert, aber Modell nicht geladen
- ausgehendes Ziel nicht in der Allowlist oder NetworkPolicy erlaubt

### Backup

Ein vollständiges Backup umfasst:

- PostgreSQL-Datenbank
- bisherige und aktive Fernet-Keys
- `WEBHOOK_LOOKUP_HMAC_KEY`
- produktive Helm-Werte ohne Klartext-Secrets
- externe Secret-Ressourcen
- bei internem Ollama optional das Modell-PVC

Redis enthält Warteschlangen und kurzlebige Ergebnisse, ist aber kein Ersatz
für PostgreSQL. Der Outbox-Zustand in PostgreSQL bleibt die dauerhafte Quelle
für noch nicht veröffentlichte Jobs.

## Statelessness und Skalierung

API und Worker speichern keine fachlichen Daten im lokalen Container-Dateisystem.
Temporäre Daten liegen in einem begrenzten `emptyDir`. Sitzungen werden nicht im
Arbeitsspeicher eines einzelnen API-Pods gehalten. Dauerhafte Daten liegen in
PostgreSQL, Queue-Zustand in Redis.

Der eingebaute Anwendungslimiter arbeitet pro API-Prozess und ist als lokale
Sicherheitsgrenze gedacht. Bei mehreren API-Replikaten stellt die
Ingress-Rate-Limitierung die externe gemeinsame Schutzschicht dar. Wer globale
fachliche Quoten benötigt, sollte einen Redis-basierten verteilten Limiter
ergänzen.

PostgreSQL, Redis und Ollama laufen im mitgelieferten Chart jeweils als einzelne
StatefulSet-Replik. Für hohe Verfügbarkeit sollten produktiv verwaltete oder
anderweitig replizierte Dienste verwendet werden.

## Projektstruktur

```text
apps/api/                         FastAPI, Dashboard und Admin-Endpunkte
apps/worker/                      Celery-Tasks
apps/mock_paperless/              Paperless-Testdienst
connectors/paperless/             Paperless-HTTP-Connector
core/config/                      Anwendungseinstellungen
core/db/                          Engine, Sessions und Migrationseinstieg
core/field_config/                Feldkonfiguration und Providerwahl
core/orchestration/               Job-Orchestrator und Phasen
core/paperless/                   Instanzverwaltung und Connector-Fabrik
core/queue/                       Celery, Outbox und Sweeper
core/security/                    Auth, Verschlüsselung, Redaction und SSRF-Schutz
deploy/helm/ezeus-ai-2/           Kubernetes-Helm-Chart
infrastructure/migrations/        Alembic-Migrationen
plugins/llm/                      Ollama-Provider
scripts/                          Administration und Smoke-Tests
tests/                            Unit- und Integrationstests
webhooks/paperless/               Paperless-Webhook-Routen
```

## Weiterführende Dokumentation

- `docs/architecture.md` für die technische Architektur
- `docs/configuration.md` für alle Einstellungen
- `docs/dashboard.md` für die Oberfläche
- `docs/paperless-integration.md` für Paperless
- `docs/security.md` für das Sicherheitsmodell
- `docs/testing.md` für Tests und CI
- `deploy/helm/ezeus-ai-2/README.md` für den Kubernetes-Betrieb

## Lizenz

Die gültigen Lizenzbedingungen ergeben sich aus den Lizenzdateien und den
Vorgaben des Repository-Eigentümers.
