# eZEUS-AI-2

## Projektbeschreibung

eZEUS-AI-2 ist eine Dokumentenverarbeitungsplattform für Paperless-ngx. Die
Anwendung nimmt Paperless-Webhooks entgegen, legt persistente
Verarbeitungsaufträge an und verarbeitet Dokumente über OCR, konfigurierbare
Extraktionsprovider und Validatoren. Ergebnisse werden nur in leere
Paperless-Felder geschrieben.

Der aktuelle Stand ist eine testbare minimale Verarbeitungspipeline und keine
freigegebene Produktionsversion.

## Ziel und Zweck

Das Projekt automatisiert die lokale Nachbearbeitung importierter
Paperless-Dokumente. PostgreSQL speichert Aufträge, Verarbeitungsphasen,
Templates, Extraktionsergebnisse und Auditdaten. Redis und Celery verteilen
Aufträge an Worker. Dokumentdaten können mit PaddleOCR, regulären Ausdrücken,
Schlüsselwörtern und optional einem lokalen Ollama-Modell verarbeitet werden.

## Hauptfunktionen

- Annahme authentifizierter Paperless-Webhooks
- Idempotente Auftragserstellung anhand einer Event-ID
- Priorisierte Celery-Warteschlangen
- OCR über einen PaddleOCR-Adapter
- Extraktion über Regex-, Keyword- und Ollama-Provider
- Validierung und Normalisierung extrahierter Werte
- Schreibschutz für bereits gefüllte Paperless-Inhalte und Custom Fields
- Versionierte Templates pro Paperless-Dokumenttyp
- Auditprotokoll für Schreiboperationen
- Betriebsdashboard und bereinigte Verarbeitungsprotokolle
- Health- und Readiness-Endpunkte

## Voraussetzungen

Für den Containerbetrieb:

- Docker Engine
- Docker Compose
- ausreichend Arbeitsspeicher und Speicherplatz für PaddleOCR
- bei Ollama-Nutzung eine vom Worker erreichbare Ollama-Instanz mit dem
  konfigurierten Modell

Für die lokale Entwicklung:

- Python 3.12 oder eine kompatible neuere Version
- eine lokale oder erreichbare Redis-Instanz für Celery
- für den vollständigen Betrieb PostgreSQL und Paperless-ngx oder der
  mitgelieferte Paperless-Mock

Die Paddle-Abhängigkeiten sind nicht Bestandteil der normalen Installation.
Der dafür vorgesehene Container verwendet Python 3.12.

## Verwendete Technologien

- Python
- FastAPI und Uvicorn
- Pydantic und pydantic-settings
- SQLAlchemy und Alembic
- PostgreSQL
- Celery und Redis
- HTTPX
- PaddleOCR als optionale OCR-Abhängigkeit
- Ollama als optionaler lokaler LLM-Dienst
- Pytest, Ruff und mypy für Entwicklung und Prüfung
- Docker und Docker Compose

## Installation

### Containerinstallation

Konfigurationsvorlage kopieren:

```bash
cp .env.example .env
```

Unter PowerShell:

```powershell
Copy-Item .env.example .env
```

Alle Beispielzugangsdaten in `.env` müssen vor einer nicht lokalen Nutzung
ersetzt werden.

### Lokale Entwicklungsinstallation

```bash
python -m venv .venv
```

Aktivierung unter Linux oder macOS:

```bash
source .venv/bin/activate
```

Aktivierung unter PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Projekt und Entwicklungsabhängigkeiten installieren:

```bash
python -m pip install -e ".[dev]"
```

Für lokale OCR-Entwicklung:

```bash
python -m pip install -e ".[dev,ocr-paddle]"
```

## Konfiguration

Die Anwendung liest ihre Konfiguration aus Umgebungsvariablen und optional aus
einer lokalen `.env`-Datei. Die vollständige Vorlage steht in
[.env.example](.env.example). Weitere Hinweise enthält
[docs/configuration.md](docs/configuration.md).

Die Werte in `.env.example` sind ausschließlich für die lokale Einrichtung
bestimmt. Bei `APP_ENV=production` lehnt die Anwendung leere, mit `example-`
beginnende und als `change-me` markierte Anwendungs-Secrets ab.

Ollama ist im mitgelieferten Compose-Stack nicht als Dienst definiert.
`OLLAMA_BASE_URL` muss daher auf eine separat betriebene und aus dem
Anwendungsnetz erreichbare Instanz zeigen.

## Umgebungsvariablen

- `APP_ENV`: Laufzeitumgebung, beispielsweise `development`, `test` oder
  `production`
- `APP_HOST`: Bind-Adresse des API-Containers
- `APP_PORT`: Port des API-Containers und veröffentlichter Host-Port
- `APP_LOG_LEVEL`: Log-Level für Uvicorn und Celery
- `DATABASE_URL`: SQLAlchemy-Verbindungsadresse
- `POSTGRES_PASSWORD`: Passwort des PostgreSQL-Compose-Dienstes
- `REDIS_URL`: Celery-Broker und Result-Backend
- `PAPERLESS_BASE_URL`: Basisadresse der Paperless-API
- `PAPERLESS_API_TOKEN`: Paperless-API-Token
- `PAPERLESS_WEBHOOK_SECRET`: gemeinsames Secret für Paperless-Webhooks
- `ADMIN_API_SECRET`: gemeinsames Secret für administrative Endpunkte
- `CREDENTIAL_ENCRYPTION_KEY`: Fernet-Schlüssel zur Verschlüsselung gespeicherter
  Paperless-Zugangsdaten
- `PAPERLESS_VERIFY_TLS`: TLS-Zertifikatsprüfung für Paperless
- `LOCAL_ONLY`: kennzeichnet den ausschließlich lokalen Betriebsmodus
- `CLOUD_AI_GLOBALLY_ALLOWED`: globale Freigabe für Cloud-AI; derzeit ist kein
  Cloud-Provider implementiert
- `OLLAMA_ENABLED`: aktiviert den Ollama-Extraktionsprovider
- `OLLAMA_BASE_URL`: Basisadresse der Ollama-API
- `OLLAMA_MODEL`: Name des lokalen Ollama-Modells
- `OLLAMA_TIMEOUT_SECONDS`: Zeitlimit eines Ollama-Aufrufs
- `OLLAMA_MAX_INPUT_CHARS`: maximale OCR-Textlänge pro Ollama-Feldextraktion
- `OLLAMA_KEEP_ALIVE`: Vorhaltezeit des Modells in Ollama
- `JOB_MAX_RETRIES`: maximale Zahl automatischer Wiederholungen
- `JOB_RETRY_DELAYS_SECONDS`: kommagetrennte Wartezeiten für Wiederholungen
- `OCR_PROVIDER`: OCR-Provider; derzeit wird `paddleocr` unterstützt
- `OCR_LANGUAGE`: OCR-Sprache
- `OCR_DEVICE`: OCR-Gerät, beispielsweise `cpu`
- `OCR_TIMEOUT_SECONDS`: Grundlage für das Celery-Zeitlimit
- `MAX_DOCUMENT_BYTES`: maximale akzeptierte Downloadgröße

## Start der Anwendung

### Docker Compose

```bash
docker compose up --build
```

Der API-Dienst führt vor dem Start `alembic upgrade head` aus. Bei der
Standardkonfiguration ist die Anwendung unter `http://localhost:8080`
erreichbar. Der Compose-Stack startet die API, den PaddleOCR-Worker,
PostgreSQL, Redis und einen lokalen Paperless-Mock.

Status prüfen:

```bash
docker compose ps
```

Container beenden:

```bash
docker compose down
```

### Lokaler API-Start

Vor dem API-Start müssen die Datenbankmigrationen ausgeführt werden:

```bash
alembic upgrade head
uvicorn apps.api.main:app --host 127.0.0.1 --port 8080
```

Der einfache Endpunkt `/health` prüft den API-Prozess. `/ready` prüft zusätzlich
Datenbank, Redis, Paperless, die OCR-Konfiguration und bei Aktivierung Ollama.

### Lokaler Worker-Start

```bash
celery -A core.queue.celery_app.celery_app worker -Q high,normal,low --loglevel=INFO
```

## Verwendung

Das Dashboard liegt am Startpfad `/`. Die OpenAPI-Dokumentation ist unter
`/docs` erreichbar. Paperless-Instanzen werden unter `/admin/instances`
verwaltet. Die Seite benötigt das `ADMIN_API_SECRET`; es wird nur im
Sitzungsspeicher des Browsers gehalten.

Einen Fernet-Schlüssel für `CREDENTIAL_ENCRYPTION_KEY` erzeugen:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Für jede angelegte Instanz zeigt die Verwaltungsseite eine eigene Webhook-URL:

```text
https://<ezeus-host>/webhooks/paperless/<instanzkennung>
```

URL, API-Token und Webhook-Secret werden pro Instanz verwaltet. API-Token und
Webhook-Secret liegen verschlüsselt in der Datenbank und werden über API und
Oberfläche nicht im Klartext ausgegeben. Die Instanzkennung trennt Dokumente
und Ereignisse verschiedener Paperless-Systeme.

Der bisherige Webhook bleibt für die globale `.env`-Konfiguration
rückwärtskompatibel:

```text
http://<host>:<port>/webhooks/paperless
```

Erforderlicher Header:

```text
X-EZEUS-Webhook-Secret: <PAPERLESS_WEBHOOK_SECRET>
```

Beispiel-Payload:

```json
{
  "document_id": 128,
  "event_id": "paperless-event-128"
}
```

Ein neuer Auftrag liefert HTTP 202. Ein bereits verarbeitetes Event liefert
HTTP 200.

Templates werden über `POST /api/templates` angelegt. Der Aufruf benötigt den
Header `X-EZEUS-Admin-Secret`. Ein minimales Template:

```json
{
  "name": "Eingangsrechnung",
  "document_type_external_id": "7",
  "is_default": true,
  "config": {
    "fields": {
      "invoice_number": {
        "target_field_id": 14,
        "providers": [
          {
            "type": "regex",
            "patterns": [
              "(?i)rechnungsnummer[\\s:]+([A-Z0-9./_-]+)"
            ]
          }
        ],
        "validators": [
          {
            "type": "required_pattern",
            "pattern": "^[A-Z0-9./_-]+$"
          }
        ]
      }
    }
  }
}
```

Das vollständige Format ist in
[docs/template-format.md](docs/template-format.md) beschrieben.

## Projektstruktur

- `apps/api`: FastAPI-Anwendung, Administrationsendpunkte und Dashboard
- `apps/worker`: Celery-Aufgabe für Dokumentenaufträge
- `apps/mock_paperless`: lokaler Paperless-API-Mock für Entwicklung
- `connectors`: Connector-Schnittstelle und Paperless-Implementierung
- `core/config`: Laufzeitkonfiguration
- `core/db`: SQLAlchemy-Basis und Sitzungsverwaltung
- `core/events`: interne Ereignismodelle
- `core/jobs`: Auftragserstellung und Statusübergänge
- `core/models`: persistente SQLAlchemy-Modelle
- `core/orchestration`: Verarbeitungspipeline
- `core/queue`: Celery-Konfiguration und Queue-Adapter
- `core/templates`: Template-Schema und Auswahl
- `core/validation`: Validierungs- und Normalisierungslogik
- `plugins`: Extraktions-, LLM-, OCR- und Validierungsbausteine
- `webhooks`: Paperless-Webhook, Schema und Secret-Prüfung
- `infrastructure/migrations`: Alembic-Konfiguration und Migrationen
- `scripts`: Hilfsskript zur Erzeugung der PDF-Testdatei
- `tests`: Unit-, API- und Integrationstests
- `docs`: ergänzende Architektur-, Betriebs- und Sicherheitsdokumentation

Die API startet über `apps.api.main:app`. Celery lädt
`core.queue.celery_app:celery_app`. Der Entwicklungs-Mock startet über
`apps.mock_paperless.main:app`.

## Tests

Vollständige Tests:

```bash
APP_ENV=test python -m pytest
```

Unter PowerShell:

```powershell
$env:APP_ENV = "test"
python -m pytest
```

Statische Prüfungen:

```bash
ruff check .
ruff format --check .
mypy apps connectors core plugins webhooks
```

Compose-Konfiguration prüfen:

```bash
docker compose config --quiet
```

Weitere Informationen stehen in [docs/testing.md](docs/testing.md).

## Fehlerbehebung

- `/health` antwortet, `/ready` liefert aber HTTP 503: Die Antwort enthält den
  Status von Datenbank, Redis, Paperless, OCR und gegebenenfalls Ollama.
- Paperless meldet HTTP 401: `PAPERLESS_API_TOKEN` und
  `PAPERLESS_BASE_URL` prüfen.
- Der Webhook meldet HTTP 401: Header und `PAPERLESS_WEBHOOK_SECRET` müssen
  übereinstimmen.
- Administrative Endpunkte melden HTTP 401: `ADMIN_API_SECRET` setzen und als
  `X-EZEUS-Admin-Secret` senden.
- PaddleOCR ist nicht installiert: das Extra `ocr-paddle` installieren oder
  `Dockerfile.paddle` verwenden.
- Das Ollama-Modell wird nicht als bereit erkannt: `OLLAMA_ENABLED`,
  `OLLAMA_BASE_URL` und `OLLAMA_MODEL` prüfen.
- Portänderungen: `APP_PORT` in `.env` setzen und den Compose-Stack neu
  erstellen.

## Sicherheitshinweise

- `.env` und lokale Varianten sind durch `.gitignore` ausgeschlossen.
- Reale Tokens, Passwörter und Schlüssel dürfen nicht versioniert oder in
  Images eingebettet werden.
- TLS-Prüfung für Paperless ist standardmäßig aktiv.
- Dashboard, Log-Endpunkt und OpenAPI-Dokumentation besitzen keine eigene
  Benutzerverwaltung. Ein produktiver Zugriff benötigt einen
  authentifizierenden TLS-Reverse-Proxy.
- Die Administrationsendpunkte verwenden ein gemeinsames Secret und keine
  rollenbasierte Autorisierung.
- Der Paperless-Mock ist ausschließlich für lokale Entwicklung und Tests
  vorgesehen.
- Container-Netze, Datenbank und Redis dürfen im Produktivbetrieb nicht
  öffentlich erreichbar sein.
- Der Quellcode enthält keine produktiven Zugangsdaten. Die Werte in
  `.env.example` sind erkennbare Platzhalter.

Weitere bekannte Sicherheitslücken und ausstehende Maßnahmen stehen in
[docs/security.md](docs/security.md) und im
[CODE_REVIEW_REPORT.md](CODE_REVIEW_REPORT.md).

## Backup und Wiederherstellung

PostgreSQL enthält die dauerhaften Aufträge, Templates, Ergebnisse und
Auditdaten. Vor einem Backup sollten API und Worker keine neuen Aufträge
annehmen.

Beispiel für ein PostgreSQL-Backup:

```bash
docker compose exec -T postgres pg_dump -U ezeus -d ezeus -Fc > ezeus.dump
```

Beispiel für die Wiederherstellung:

```bash
docker compose exec -T postgres pg_restore -U ezeus -d ezeus --clean --if-exists < ezeus.dump
```

Die lokale `.env`-Datei muss getrennt und verschlüsselt gesichert werden. Das
Redis-Volume enthält Warteschlangen- und Ergebniszustand, ist aber nicht die
führende fachliche Datenquelle. Das Volume `ocr_models` kann neu aufgebaut
werden, sofern die benötigten Modelle weiterhin verfügbar sind.

Eine Wiederherstellung muss zunächst in einer getrennten Umgebung getestet
werden.

## Entwicklung und Erweiterung

- Neue Extraktionsprovider implementieren `ExtractionProvider` aus
  `plugins/base/interfaces.py`.
- Neue OCR-Provider implementieren `OCRProvider` und werden in
  `plugins/ocr/factory.py` registriert.
- Neue Template-Provider und Validatornamen müssen in
  `core/templates/schema.py` freigegeben werden.
- Datenbankänderungen benötigen eine Alembic-Migration.
- Änderungen an Connectoren müssen den Schutz bereits gefüllter
  Paperless-Felder erhalten.
- Vor jeder Übernahme müssen Tests, Ruff, Formatter und mypy erfolgreich
  ausgeführt werden.

## Bekannte Einschränkungen

- Die Anwendung unterstützt genau eine konfigurierte Paperless-Instanz.
- Der Compose-Stack ist eine Entwicklungsumgebung und enthält einen Mock statt
  eines produktiven Paperless-Dienstes.
- Referenzdaten aus Paperless werden nicht lokal synchronisiert.
- Die Administrations-API besitzt keine rollenbasierte Autorisierung.
- Dashboard und Log-API sind innerhalb der Anwendung nicht authentifiziert.
- PaddleOCR-Modelle können beim ersten Worker-Start heruntergeladen werden.
- Ollama ist nicht Bestandteil des Compose-Stacks.
- Die Dashboard-Karten nennen fest Qwen3:4b und PaddleOCR und spiegeln
  abweichende Laufzeitkonfigurationen nicht dynamisch wider.
- Die Regex-Laufzeitprüfung kann einen einzelnen bereits laufenden regulären
  Ausdruck nicht unterbrechen.
- Datenbankstatus und Celery-Nachricht werden nicht über eine gemeinsame
  Transaktion oder eine Outbox koordiniert.
- Es gibt noch keine Last-, Malware-, PDF-Bomb- oder vollständigen
  End-to-End-Sicherheitstests.

## Lizenz

Im Repository ist derzeit keine Lizenzdatei vorhanden. Ohne ausdrückliche
Lizenz werden keine Nutzungs-, Änderungs- oder Weitergaberechte eingeräumt.
