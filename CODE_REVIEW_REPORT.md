# Code Review Report

## Erweiterung: mehrere Paperless-Instanzen

Die Anwendung unterstützt zusätzlich zur bisherigen globalen
Paperless-Konfiguration mehrere unabhängig verwaltete Paperless-Instanzen.

- `core/models/paperless_instance.py`: neues persistentes Instanzmodell mit
  Kennung, Basis-URL, TLS-Einstellung und Aktivstatus.
- `core/security/credentials.py`: Fernet-Verschlüsselung für API-Tokens und
  Webhook-Secrets. Klartext-Zugangsdaten werden nicht über die API ausgegeben.
- `infrastructure/migrations/versions/0003_paperless_instances.py`: additive
  Datenbankmigration ohne Änderung vorhandener Dokumente oder Jobs.
- `apps/api/paperless_instances.py`: geschützte Verwaltungsseite und
  Administrations-API zum Anlegen, Anzeigen, Ändern und Testen von Instanzen.
- `webhooks/paperless/router.py`: instanzbezogene Webhooks unter
  `/webhooks/paperless/<kennung>` mit eigenem Secret.
- `core/paperless/service.py` und `core/orchestration/orchestrator.py`:
  automatische Auswahl der Quellinstanz für den gesamten Lese- und
  Schreibvorgang.
- `connectors/paperless/connector.py`: explizite Zugangsdaten je
  Connector-Instanz bei weiterhin vorhandener `.env`-Kompatibilität.

Sicherheitswirkung:

- API-Tokens und Webhook-Secrets werden verschlüsselt in PostgreSQL abgelegt.
- `CREDENTIAL_ENCRYPTION_KEY` ist im Produktionsmodus verpflichtend.
- Listenantworten und Verwaltungsoberfläche geben keine Zugangsdaten zurück.
- Dokument- und Event-IDs werden mit der Instanzkennung getrennt, sodass
  Überschneidungen verschiedener Paperless-Systeme keine falsche Zuordnung
  verursachen.

Validierung:

- 21 Python-Tests bestanden.
- Ruff-Lint und Ruff-Formatprüfung bestanden.
- mypy im strikten Modus bestanden.
- Eine externe Starlette-Abkündigungswarnung zur TestClient-Integration bleibt
  bestehen und beeinflusst die Funktion nicht.

## Prüfrahmen

- Repository: `ezeus-AI-2`
- geprüfter Branch: `local/qwen3-ollama`
- Ausgangsrevision: `aa5c684`
- Prüfdatum: 28. Juli 2026
- ursprünglich versionierte Dateien: 109
- ursprünglich erkannte Python-Dateien: 87, einschließlich leerer
  Paketdateien
- ursprünglicher Git-Zustand: sauber

Alle zu Beginn versionierten Dateien wurden nach Struktur, Inhalt,
Abhängigkeiten, Startpunkten, Tests, Dokumentation und Konfiguration geprüft.
Binäre Inhalte wurden hinsichtlich Ablage und Zweck geprüft, aber nicht als
Quelltext interpretiert. Neu angelegte Test- und Berichtsdateien wurden in die
abschließenden Prüfungen einbezogen.

## Zusammenfassung des ursprünglichen Projektzustands

Das Repository enthielt eine klar erkennbare Python-Anwendung mit folgenden
Komponenten:

- FastAPI-API unter `apps/api/main.py`
- Celery-Worker unter `apps/worker/tasks.py`
- lokaler Paperless-Mock unter `apps/mock_paperless/main.py`
- SQLAlchemy-Modelle und Alembic-Migrationen
- Paperless-Connector
- Regex-, Keyword-, Ollama- und PaddleOCR-Provider
- Dashboard mit eingebettetem HTML, CSS und JavaScript
- 17 automatisierte Tests
- Dockerfiles und Docker-Compose-Konfiguration
- README und ergänzende Dokumentation

Der Git-Zustand war sauber. Lokale `__pycache__`- und `.pyc`-Dateien waren
vorhanden, aber korrekt ignoriert und nicht versioniert. Der Linter und mypy
waren bereits ohne Befund. Der Formatter erkannte zehn nicht einheitlich
formatierte Dateien. Die Entwicklungswerkzeuge waren in der lokalen
Python-Installation zunächst nicht installiert.

## Gefundene Probleme

### Funktion und Konfiguration

- `apps/mock_paperless/main.py` erwartete einen fest codierten Token, der nicht
  zum Wert aus `.env.example` passte. Der dokumentierte Compose-Schnellstart
  konnte deshalb die Readiness-Prüfung des Paperless-Mocks nicht bestehen.
- `APP_HOST`, `APP_PORT` und `APP_LOG_LEVEL` waren deklariert, wurden von den
  Container-Startbefehlen aber nicht verwendet.
- Die Dokumentation beschrieb den automatisierten Integrationstest teilweise
  als vollständigen Container-End-to-End-Test, obwohl er isolierte
  Testimplementierungen für Connector und OCR verwendet.
- Das Dashboard nennt Qwen3:4b und PaddleOCR fest, auch wenn die
  Laufzeitkonfiguration abweicht.

### Codequalität und Struktur

- Acht kurze Docstrings wiederholten nur die jeweilige Klassen- oder
  Methodensignatur.
- Sieben leere `__init__.py`-Dateien markierten Dokumentations- oder
  Platzhalterverzeichnisse als Python-Pakete, obwohl dort kein Python-Code
  vorhanden war.
- Drei direkte Laufzeitabhängigkeiten hatten keine Verwendung im
  versionierten Code.
- Mehrere Python-Dateien enthielten gemischte Zeilenenden oder entsprachen
  nicht vollständig dem konfigurierten Ruff-Format.
- Die Zeilenenden waren in `.gitattributes` nicht ausdrücklich festgelegt.

### Sicherheit

- `core/orchestration/orchestrator.py` verwendete den von Paperless gelieferten
  Dateinamen direkt beim Anlegen einer temporären Datei. Pfadbestandteile
  konnten dadurch das vorgesehene temporäre Verzeichnis verlassen.
- Der Produktionsvalidator akzeptierte die in `.env.example` verwendeten
  `example-`-Zugangsdaten.
- Die deklarierte Pytest-8-Reihe enthielt laut `pip-audit` die bekannte
  Schwachstelle `PYSEC-2026-1845`.
- Dashboard, Log-API und OpenAPI-Dokumentation besitzen keine
  anwendungsinterne Authentifizierung.
- Die Administrations-API verwendet ein gemeinsames Secret ohne
  rollenbasierte Autorisierung.
- Downloads werden erst nach dem vollständigen Einlesen in den Speicher auf
  ihre Größe geprüft.
- Die Regex-Laufzeitprüfung kann einen bereits laufenden, teuren regulären
  Ausdruck nicht unterbrechen.
- Datenbankstatus und Celery-Nachricht werden nicht atomar über eine Outbox
  koordiniert.
- Rate Limiting, Malware-Prüfung, PDF-Bomb-Schutz und eine administrativ
  eingeschränkte Zieladressliste fehlen.
- Der Worker startet zur Berechtigungsanpassung des OCR-Modell-Volumes als
  Root und wechselt erst danach zum Benutzer `ezeus`.
- Bandit meldet die Standard-Bind-Adresse `0.0.0.0` mit mittlerer Schwere. Die
  Bind-Adresse ist für den Containerbetrieb beabsichtigt und jetzt über
  `APP_HOST` konfigurierbar.

### Vertrauliche Daten

Es wurden keine echten API-Schlüssel, privaten Schlüssel, Passwörter oder
Tokens im versionierten Bestand gefunden. `.env.example` enthält erkennbare
Beispielwerte. Der Fallback-Token des lokalen Paperless-Mocks ist ausschließlich
für Entwicklung und Tests bestimmt.

## Entfernte Kommentare

Insgesamt wurden acht redundante Docstring-Zeilen entfernt:

- sechs selbsterklärende Exception-Docstrings in
  `connectors/base/errors.py`
- ein redundanter Klassen-Docstring in `plugins/ocr/adapter.py`
- ein redundanter Methodendocstring in `plugins/ocr/interfaces.py`

Der Typprüfungshinweis am Celery-Decorator in `apps/worker/tasks.py` blieb
erhalten, weil er eine konkrete technische Einschränkung des Decorator-Typings
dokumentiert. Es waren keine veralteten TODO-, FIXME-, HACK- oder
auskommentierten Codeblöcke vorhanden.

## Entfernte Emojis und Sonderzeichen

- entfernte Emojis: 0
- entfernte dekorative Sonderzeichen: 4

Im Dashboard wurden zwei typografische Auslassungszeichen durch drei Punkte und
zwei typografische Platzhalterstriche durch normale Bindestriche ersetzt. Im
restlichen versionierten Bestand wurden keine Emojis, schwarzen KI-Punkte oder
vergleichbaren Aufzählungssymbole gefunden.

## Bereinigte oder entfernte Dateien

Folgende leere Paketmarker wurden entfernt:

- `core/services/__init__.py`
- `docs/__init__.py`
- `docs/architecture/__init__.py`
- `docs/benchmarks/__init__.py`
- `docs/deployment/__init__.py`
- `docs/specification/__init__.py`
- `infrastructure/docker/__init__.py`

Die lokalen `__pycache__`-Verzeichnisse wurden nicht verändert, weil sie
bereits korrekt ignoriert sind und nicht zum versionierten Repository gehören.
Vom Paketbau erzeugte lokale Build- und Egg-Info-Artefakte wurden nach der
Prüfung wieder entfernt. Die temporäre `.env`-Datei und die temporären
SQLite-Datenbanken wurden ebenfalls entfernt.

## Verbesserte Codebereiche

### `core/orchestration/orchestrator.py`

- Art: Sicherheitshärtung des temporären Dateipfads
- Grund: Externe Dateinamen dürfen keine Pfadnavigation bewirken.
- Änderung: Backslashes werden normalisiert, anschließend wird nur der
  Basisname verwendet. Leere oder ungültige Namen fallen auf `document.bin`
  zurück.
- Mögliche Auswirkung: Dokumente mit Pfadbestandteilen werden weiterhin
  verarbeitet, aber ausschließlich unter dem sicheren Basisnamen.

### `apps/mock_paperless/main.py`

- Art: Konfigurationsbereinigung
- Grund: Der Mock-Token widersprach `.env.example`.
- Änderung: Der Mock verwendet `PAPERLESS_API_TOKEN`; ohne Konfiguration bleibt
  der bisherige Mock-Fallback erhalten.
- Mögliche Auswirkung: Der dokumentierte lokale Compose-Stack kann mit einer
  aus `.env.example` erzeugten Konfiguration authentifizieren.

### `core/config/settings.py`

- Art: Produktionsvalidierung
- Grund: Beispielzugangsdaten durften nicht als produktive Werte akzeptiert
  werden.
- Änderung: Leere Werte, `change-me`, Werte mit dem Präfix `example-` und eine
  entsprechende Beispiel-Datenbank-URL werden im Produktionsmodus abgelehnt.
- Mögliche Auswirkung: Bestehende Produktionskonfigurationen mit erkennbaren
  Platzhalterwerten starten nicht mehr und müssen sichere Werte erhalten.

### `docker-compose.yml`, `Dockerfile`, `Dockerfile.paddle`

- Art: Beseitigung fest codierter Startparameter
- Grund: Deklarierte Host-, Port- und Log-Level-Werte waren wirkungslos.
- Änderung: API und Worker verwenden `APP_HOST`, `APP_PORT` und
  `APP_LOG_LEVEL`. Portfreigabe und API-Healthcheck berücksichtigen
  `APP_PORT`.
- Mögliche Auswirkung: Standardwerte bleiben unverändert. Abweichende
  Konfigurationen werden jetzt wirksam.

### `apps/api/dashboard.py`

- Art: Oberflächenbereinigung
- Grund: Dekorative typografische Sonderzeichen sollten entfernt werden.
- Änderung: Ausschließlich textuelle Platzhalter wurden ersetzt.
- Mögliche Auswirkung: Keine funktionale Auswirkung.

### Formatierte Python-Dateien

Ruff standardisierte Formatierung und Zeilenenden unter anderem in:

- `apps/api/main.py`
- `connectors/paperless/connector.py`
- `core/models/job.py`
- `core/templates/schema.py`
- `plugins/llm/ollama.py`
- `tests/unit/test_ollama_provider.py`
- `tests/unit/test_template_schema.py`

Die Änderungen sind mechanisch und verändern das Laufzeitverhalten nicht.

### `.gitattributes`

- Art: Repository-Hygiene
- Grund: Plattformabhängige Zeilenenden führten zu unnötigem Diff-Rauschen.
- Änderung: Textdateien werden ausdrücklich mit LF geführt.
- Mögliche Auswirkung: Neue Checkouts verwenden einheitliche Zeilenenden.

## Geänderte Abhängigkeiten

Entfernte direkte Laufzeitabhängigkeiten:

- `python-multipart`, da keine Formular- oder Datei-Upload-Endpunkte vorhanden
  sind
- `structlog`, da es nicht importiert oder konfiguriert wird
- `PyYAML`, da der Anwendungscode keine YAML-Dateien verarbeitet

`PyYAML` kann weiterhin transitiv über `uvicorn[standard]` installiert werden.

Gezielt aktualisierte Entwicklungsabhängigkeiten:

- `pytest` von `>=8.3,<9` auf `>=9.0.3,<10`
- `pytest-asyncio` von `>=0.25,<1` auf `>=1.3,<2`

Grund war die von `pip-audit` gemeldete Pytest-Schwachstelle und die notwendige
Kompatibilität zwischen Pytest und pytest-asyncio. Nach der Aktualisierung
bestanden alle Tests. Es wurden keine Laufzeit-Major-Versionen aktualisiert.

Ein Lockfile ist weiterhin nicht vorhanden. Die vorhandenen
Versionsobergrenzen verhindern unkontrollierte Laufzeit-Major-Updates, liefern
aber keine vollständig reproduzierbare Auflösung.

## Dokumentation

`README.md` wurde vollständig neu strukturiert und anhand des Quellcodes
überarbeitet. Enthalten sind:

- Projektbeschreibung, Ziel und Funktionen
- Voraussetzungen und Technologien
- Container- und lokale Installation
- vollständige Konfigurations- und Umgebungsvariablenübersicht
- API-, Worker- und Compose-Start
- Webhook- und Template-Beispiele
- Projektstruktur und Startpunkte
- Test-, Lint-, Typ- und Compose-Prüfungen
- Fehlerbehebung
- Sicherheitshinweise
- Backup und Wiederherstellung
- Erweiterungspunkte
- bekannte Einschränkungen
- Lizenzstatus

Zusätzlich wurden `docs/configuration.md`, `docs/deployment.md`,
`docs/security.md` und `docs/testing.md` an das tatsächliche Verhalten
angepasst.

## Neue Tests

### `tests/test_mock_paperless.py`

Prüft, dass der Paperless-Mock den konfigurierten API-Token akzeptiert und
einen falschen Token ablehnt.

### `tests/unit/test_settings.py`

Prüft, dass der Produktionsmodus Beispielzugangsdaten ablehnt.

Der bestehende Integrationstest prüft zusätzlich, dass ein externer Dateiname
mit Pfadnavigation nur als sicherer Basisname im temporären OCR-Verzeichnis
gespeichert wird.

## Ausgeführte Prüfungen und Ergebnisse

### Baseline

- Python: 3.14.6
- Pytest: 17 Tests bestanden, 47 externe Abkündigungswarnungen
- Ruff Lint: bestanden
- Ruff Format: zehn Dateien nicht einheitlich
- mypy strict: bestanden

### Abschluss

- `python -m pytest`: 19 Tests bestanden, eine externe
  Starlette-Abkündigungswarnung
- `ruff check .`: bestanden
- `ruff format --check .`: bestanden
- `mypy apps connectors core plugins webhooks`: bestanden, 64 Quelldateien
- `pip check`: bestanden
- `pip-audit --local`: keine bekannte Schwachstelle gefunden
- `bandit -r apps connectors core plugins webhooks`: ein akzeptierter
  Medium-Hinweis für die konfigurierbare Container-Bind-Adresse `0.0.0.0`,
  keine High-Hinweise
- Secret-Mustersuche: keine produktiven Secrets gefunden
- Suche nach TODO, FIXME, HACK, Emojis und auffälligen Symbolen: ohne
  verbleibenden Befund
- `docker compose config --quiet`: bestanden
- Alembic `upgrade head` auf temporärem SQLite: bestanden
- Alembic-Revisionsstand: `0002_repair_initial_schema`
- Tabelleninspektion: `alembic_version`, `audit_entries`, `documents`,
  `extraction_results`, `job_phases`, `jobs`, `templates`
- Python-Paketbau: Source-Archiv und Wheel erfolgreich
- lokaler Uvicorn-Start: erfolgreich
- `GET /health`: HTTP 200 mit Status `ok`
- `git diff --check`: keine Whitespace-Fehler

## Build-Ergebnis

Der Python-Paketbau war erfolgreich:

- `ezeus_ai_2-0.2.0.tar.gz`
- `ezeus_ai_2-0.2.0-py3-none-any.whl`

Die Artefakte wurden außerhalb des Repositories erzeugt. Lokale
Zwischenartefakte im Repository wurden entfernt.

Die Docker-Compose-Konfiguration ist gültig. Der Docker-Image-Build konnte
nicht ausgeführt werden, weil der Docker-Desktop-Linux-Daemon auf dem
Prüfrechner nicht lief. CLI und Compose waren installiert. Es liegt daher kein
verifiziertes Container-Build-Ergebnis vor.

## Nicht gelöste Probleme

- Der vollständige Compose-Stack und ein echter PaddleOCR-Lauf wurden wegen
  des nicht laufenden Docker-Daemons nicht geprüft.
- `/ready` wurde nicht gegen echte PostgreSQL-, Redis-, Paperless- und
  Ollama-Dienste geprüft.
- Die Starlette-TestClient-Integration meldet eine externe
  Abkündigungswarnung zur künftigen HTTPX-Integration.
- Dashboard, Log-API und OpenAPI-Dokumentation benötigen für Produktion einen
  authentifizierenden Reverse Proxy.
- Rollenbasierte Autorisierung, Rate Limiting, SSRF-Einschränkung,
  Malware-Prüfung und Betriebssystem-Ressourcenlimits fehlen.
- Downloadgrößen werden nicht während des Streamings begrenzt.
- Die Regex-Laufzeitbegrenzung unterbricht keinen einzelnen laufenden
  Ausdruck.
- Datenbank und Celery sind nicht über eine Outbox koordiniert.
- Der Worker benötigt für die Volume-Berechtigung einen kurzen Root-Start.
- Das Dashboard zeigt konfigurierte Provider und Modelle nicht dynamisch.
- Es gibt kein Lockfile und keine automatisierte Container- oder
  Secret-Scan-Pipeline.
- Das Repository enthält keine Lizenzdatei.

## Empfohlene weitere Schritte

1. Docker-Daemon starten und `docker compose build`, `docker compose up -d`,
   `docker compose ps` sowie einen vollständigen Webhook-Ablauf ausführen.
2. Einen automatisierten Container-End-to-End-Test mit PostgreSQL, Redis,
   Celery, Mock-Paperless und optional PaddleOCR ergänzen.
3. Einen authentifizierenden TLS-Reverse-Proxy und Rate Limiting verbindlich
   in einer Produktionskonfiguration bereitstellen.
4. Eine transaktionale Outbox für Datenbank- und Queue-Koordination prüfen.
5. Downloads streamen und die Größenbegrenzung während des Empfangs
   durchsetzen.
6. Regex-Ausführung in einen begrenzten Prozess oder eine Engine mit echter
   Zeitunterbrechung verlagern.
7. Rollenbasierte Autorisierung für administrative Endpunkte ergänzen.
8. Dependency-, Container-, SBOM- und Secret-Scanning in CI aufnehmen.
9. Reproduzierbare Abhängigkeitsauflösung über ein geeignetes Lock- oder
   Constraints-Verfahren einführen.
10. Lizenz und zulässige Nutzung des Projekts festlegen.

## Kennzahlen

- geprüfte ursprüngliche Dateien: 109
- geänderte, entfernte oder neu angelegte Dateien einschließlich dieses
  Berichts: 32
- entfernte Kommentarzeilen: 8
- entfernte Emojis: 0
- entfernte dekorative Sonderzeichen: 4
- entfernte ungenutzte Codebereiche: 0
- entfernte leere Platzhalterdateien: 7
- entfernte direkte ungenutzte Abhängigkeiten: 3
- neu angelegte Dateien: 3

Es wurden keine ungenutzten Funktionen, Imports oder Variablen entfernt, weil
Ruff und die manuelle Referenzprüfung dafür keinen sicheren Befund lieferten.
Bewusst vorbereitete Plugin-Schnittstellen blieben erhalten.
