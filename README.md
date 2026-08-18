# eZEUS-AI-2

eZEUS-AI-2 ist eine automatisierte Verarbeitungspipeline für [Paperless-ngx](https://docs.paperless-ngx.com/). Sobald in Paperless ein neues Dokument auftaucht, holt sich eZEUS die Datei, liest den Text per OCR aus, extrahiert einzelne Felder (z. B. Rechnungsnummer, Betrag, Datum) anhand konfigurierbarer Regeln oder optional per lokalem KI-Modell, validiert die Ergebnisse und schreibt sie zurück nach Paperless — ohne jemals vorhandene oder manuell gesetzte Werte zu überschreiben.

Alles läuft lokal (eigener Server, eigenes Docker-Netz). Es gibt standardmäßig keine Verbindung zu Cloud-Diensten.

---

## Inhaltsverzeichnis

1. [Voraussetzungen](#1-voraussetzungen)
2. [Aufbau des Systems](#2-aufbau-des-systems)
3. [Installation Schritt für Schritt](#3-installation-schritt-für-schritt)
4. [Konfiguration (.env)](#4-konfiguration-env)
5. [Verbindung zu Paperless-ngx einrichten](#5-verbindung-zu-paperless-ngx-einrichten)
6. [Erste Extraktions-Vorlage (Template) anlegen](#6-erste-extraktions-vorlage-template-anlegen)
7. [Betrieb prüfen (Health-Checks, Dashboard)](#7-betrieb-prüfen-health-checks-dashboard)
8. [Detaillierter Ablauf: Was passiert wann, wo und wie](#8-detaillierter-ablauf-was-passiert-wann-wo-und-wie)
9. [Fehgeschlagene Jobs & Wiederholung](#9-fehlgeschlagene-jobs--wiederholung)
10. [Bekannte Einschränkungen](#10-bekannte-einschränkungen)

---

## 1. Voraussetzungen

| Komponente | Version / Hinweis |
|---|---|
| Docker + Docker Compose | aktuelle Version, Compose v2 |
| Laufende Paperless-ngx-Instanz | erreichbar per HTTP(S) vom eZEUS-Server aus |
| Paperless API-Token | wird unter Paperless → Einstellungen → API-Token erzeugt |
| Freier Arbeitsspeicher | mind. 4 GB (PaddleOCR + optional Ollama brauchen RAM) |
| Optional: NVIDIA-GPU | nur nötig, wenn OCR/Ollama auf GPU statt CPU laufen sollen |

eZEUS bringt in seiner `docker-compose.yml` **keine echte Paperless-Instanz** mit — dort läuft standardmäßig nur ein *Mock-Paperless* für Tests/Entwicklung. Für den echten Betrieb zeigt eZEUS auf eure bestehende Paperless-ngx-Installation (per `PAPERLESS_BASE_URL`, siehe Abschnitt 4).

---

## 2. Aufbau des Systems

eZEUS besteht aus mehreren Containern, die zusammenspielen:

```
                         ┌─────────────────────┐
   Paperless-ngx  ─────► │   api (FastAPI)      │  nimmt Webhooks entgegen,
   (Webhook bei          │   Port 8080          │  stellt Admin-API & Dashboard
   neuem Dokument)       └──────────┬───────────┘  bereit
                                    │ legt Job an, reiht ihn ein
                                    ▼
                          ┌──────────────────┐
                          │   redis           │  Warteschlange (Queue)
                          └──────────┬────────┘
                                    │
                                    ▼
                          ┌──────────────────┐       ┌─────────────────┐
                          │   worker (Celery) │──────►│  Paperless-ngx   │
                          │   OCR + Extraktion│       │  (Datei holen,   │
                          │   + Validierung   │◄──────│   Werte schreiben)│
                          └──────────┬────────┘       └─────────────────┘
                                    │
                                    ▼
                          ┌──────────────────┐
                          │   postgres        │  speichert Jobs, Templates,
                          │                   │  Extraktionsergebnisse, Audit-Log
                          └──────────────────┘

                          (optional, nur wenn aktiviert)
                          ┌──────────────────┐
                          │   ollama          │  lokales KI-Modell für
                          │                   │  komplexere Extraktionsfälle
                          └──────────────────┘
```

**Wichtig:** Die `api` nimmt den Webhook nur entgegen und legt einen Auftrag (Job) an. Die eigentliche Verarbeitung (Datei holen, OCR, Extraktion, Schreiben) passiert **komplett getrennt** im `worker`-Container. Das hält die Webhook-Antwort schnell und macht das System robust gegen Lastspitzen.

---

## 3. Installation Schritt für Schritt

### 3.1 Repository holen

```bash
git clone https://github.com/floridafischet-hash/eZEUS-AI-2.git
cd eZEUS-AI-2
```

### 3.2 Umgebungsdatei anlegen

```bash
cp .env.example .env
```

Danach `.env` öffnen und **mindestens folgende Werte ändern** (siehe Abschnitt 4 für die vollständige Liste):

- `POSTGRES_PASSWORD`
- `PAPERLESS_BASE_URL`
- `PAPERLESS_API_TOKEN`
- `PAPERLESS_WEBHOOK_SECRET`
- `ADMIN_API_SECRET`

> Alle vier Secrets müssen sich vom Beispielwert unterscheiden. Startet eZEUS mit `APP_ENV=production` und einem noch unveränderten Beispiel-Secret, verweigert die Anwendung absichtlich den Start (Sicherheitsmaßnahme).

### 3.3 Container bauen und starten

```bash
docker compose build
docker compose up -d
```

Das startet: `api`, `worker`, `postgres`, `redis` (und im Standard-Compose-File zusätzlich ein Mock-Paperless für Testzwecke — für den echten Betrieb könnt ihr diesen Dienst ignorieren oder aus der Compose-Datei entfernen, sobald `PAPERLESS_BASE_URL` auf eure echte Instanz zeigt).

### 3.4 Datenbank-Migrationen

Die Migrationen laufen beim Start des `api`-Containers automatisch (`alembic upgrade head` ist Teil des Start-Kommandos). Manuell nachziehen, falls nötig:

```bash
docker compose exec api alembic upgrade head
```

### 3.5 Health-Check

```bash
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

`/ready` prüft zusätzlich Datenbank, Redis, Paperless-Erreichbarkeit, OCR-Verfügbarkeit und — falls aktiviert — Ollama. Erst wenn hier alles `true` zurückgibt, ist das System vollständig betriebsbereit.

---

## 4. Konfiguration (.env)

| Variable | Bedeutung |
|---|---|
| `APP_ENV` | `development` oder `production`. In `production` werden Beispiel-Secrets abgelehnt. |
| `APP_HOST` / `APP_PORT` | Bind-Adresse der API (Standard `0.0.0.0:8080`) |
| `APP_LOG_LEVEL` | Log-Level, z. B. `INFO` |
| `POSTGRES_PASSWORD` | Passwort für die interne Datenbank |
| `DATABASE_URL` | Vollständige DB-Verbindung (muss zum Passwort passen) |
| `REDIS_URL` | Verbindung zur Warteschlange |
| `PAPERLESS_BASE_URL` | URL eurer Paperless-ngx-Instanz, z. B. `https://paperless.meinefirma.local` |
| `PAPERLESS_API_TOKEN` | API-Token aus Paperless (zum Lesen/Schreiben von Dokumenten) |
| `PAPERLESS_WEBHOOK_SECRET` | Gemeinsames Geheimnis, das Paperless bei jedem Webhook-Aufruf mitschickt |
| `PAPERLESS_VERIFY_TLS` | TLS-Zertifikatsprüfung bei HTTPS-Verbindung zu Paperless |
| `ADMIN_API_SECRET` | Geheimnis für Admin-Endpunkte (Templates anlegen, Jobs erneut anstoßen) |
| `LOCAL_ONLY` | Wenn `true`: keine Cloud-KI-Anbindung möglich, egal was sonst konfiguriert ist |
| `CLOUD_AI_GLOBALLY_ALLOWED` | Muss `false` bleiben, solange `LOCAL_ONLY=true` — sonst verweigert die Anwendung den Start |
| `OLLAMA_ENABLED` | Schaltet die lokale KI-Extraktion frei (`true`/`false`) |
| `OLLAMA_BASE_URL` | Adresse des Ollama-Dienstes |
| `OLLAMA_MODEL` | Modellname, z. B. `qwen3:4b` |
| `OLLAMA_TIMEOUT_SECONDS` | Maximale Wartezeit auf eine KI-Antwort |
| `OLLAMA_MAX_INPUT_CHARS` | Wie viel Dokumenttext maximal an das Modell geschickt wird (längerer Text wird gekürzt) |
| `JOB_MAX_RETRIES` | Wie oft ein fehlgeschlagener Job automatisch wiederholt wird |
| `JOB_RETRY_DELAYS_SECONDS` | Wartezeiten zwischen den Wiederholungsversuchen, z. B. `30,120,600` |
| `OCR_TIMEOUT_SECONDS` | Maximale Laufzeit der Texterkennung pro Dokument |
| `MAX_DOCUMENT_BYTES` | Obergrenze für Dateigröße (Standard ca. 100 MB) |

---

## 5. Verbindung zu Paperless-ngx einrichten

1. In Paperless-ngx unter **Einstellungen → API-Token** einen neuen Token erzeugen, in `PAPERLESS_API_TOKEN` eintragen.
2. Ein beliebiges, ausreichend langes Zufalls-Geheimnis erzeugen (z. B. `openssl rand -hex 32`) und in **beiden** Systemen identisch hinterlegen:
   - in eZEUS: `PAPERLESS_WEBHOOK_SECRET`
   - in Paperless-ngx: als Header-Wert für den Webhook (z. B. `X-EZEUS-Webhook-Secret`)
3. In Paperless-ngx einen Webhook auf neue Dokumente einrichten, der bei jedem neuen Dokument einen `POST`-Request sendet an:

   ```
   http://<ezeus-host>:8080/webhooks/paperless
   ```

   mit dem Body:
   ```json
   {"document_id": 128, "event_id": "eine-eindeutige-id"}
   ```

   und dem Header `X-EZEUS-Webhook-Secret: <euer Geheimnis>`.

4. Testen: Ein Testdokument in Paperless hochladen und prüfen, ob im eZEUS-Dashboard (`http://<ezeus-host>:8080/`) ein neuer Job auftaucht.

---

## 6. Erste Extraktions-Vorlage (Template) anlegen

Eine Vorlage legt fest, welche Felder aus welchem Dokumenttyp wie extrahiert und geprüft werden. Angelegt wird sie über die Admin-API (`ADMIN_API_SECRET` erforderlich):

```bash
curl -X POST http://localhost:8080/api/templates \
  -H "X-EZEUS-Admin-Secret: <euer Admin-Secret>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Standard-Rechnung",
    "document_type_external_id": "invoice",
    "is_default": true,
    "config": {
      "fields": {
        "invoice_number": {
          "target_field_id": 12,
          "providers": [
            {"type": "regex", "patterns": ["Rechnungsnummer:\\s*(\\S+)"]}
          ],
          "validators": [
            {"type": "not_empty"}
          ]
        },
        "total": {
          "target_field_id": 15,
          "providers": [
            {"type": "regex", "patterns": ["Gesamtbetrag:\\s*([\\d.,]+\\s*EUR)"]}
          ],
          "validators": [
            {"type": "monetary_amount"}
          ]
        }
      }
    }
  }'
```

Wichtige Punkte:
- `document_type_external_id` muss dem Dokumenttyp entsprechen, den Paperless-ngx dem Dokument zuweist.
- Pro Dokumenttyp darf es nur **eine aktive Standard-Vorlage** (`is_default: true`) geben — ein zweiter Versuch schlägt bewusst mit Fehler `409` fehl.
- `target_field_id` ist die ID des Zielfeldes/benutzerdefinierten Feldes in Paperless-ngx.
- Verfügbare Extraktions-Provider: `regex`, `keyword`, `ollama` (letzterer nur bei `OLLAMA_ENABLED=true`).
- Verfügbare Validatoren u. a.: `not_empty`, `required_pattern`, `date`, `monetary_amount`, `iban`, `allowed_values`, `length`, `numeric_range`.

Für andere Dokumentarten (z. B. Lieferscheine) einfach eine weitere Vorlage mit passendem `document_type_external_id` und eigenen Feldregeln anlegen — das System ist nicht auf Rechnungen beschränkt.

---

## 7. Betrieb prüfen (Health-Checks, Dashboard)

| Endpunkt | Zweck |
|---|---|
| `GET /health` | Einfacher Lebenszeichen-Check |
| `GET /ready` | Prüft Datenbank, Redis, Paperless-Erreichbarkeit, OCR und ggf. Ollama |
| `GET /` | Web-Dashboard mit Übersicht laufender/fehlgeschlagener Jobs |
| `GET /api/logs` | Log-/Audit-Einträge (nur Metadaten, keine Dokumentinhalte) |
| `GET /docs` | Automatisch generierte API-Dokumentation (Swagger UI) |

---

## 8. Detaillierter Ablauf: Was passiert wann, wo und wie

Diese Beschreibung geht Schritt für Schritt durch die komplette Verarbeitung eines einzelnen Dokuments, von Paperless-ngx bis zurück nach Paperless-ngx.

### Schritt 1 — Paperless-ngx meldet ein neues Dokument (wo: Paperless-ngx)

Ein Dokument wird in Paperless-ngx hinzugefügt — egal ob per Scan, manuellem Upload oder E-Mail-Import. Paperless-ngx sendet daraufhin **selbst** einen `POST`-Request an eZEUS:

```
POST http://<ezeus-host>:8080/webhooks/paperless
Header: X-EZEUS-Webhook-Secret: <geheimnis>
Body:   {"document_id": 128, "event_id": "paperless-event-128"}
```

Wichtig: **In diesem Request steckt nicht die Datei selbst**, nur die Dokument-ID und eine Ereignis-ID. eZEUS weiß an dieser Stelle noch nichts über den Inhalt des Dokuments.

### Schritt 2 — Webhook wird geprüft (wo: eZEUS `api`-Container)

Der Webhook-Handler vergleicht das mitgeschickte Geheimnis mit dem konfigurierten `PAPERLESS_WEBHOOK_SECRET`. Der Vergleich erfolgt zeitkonstant (nicht per einfachem `==`), damit ein Angreifer das Geheimnis nicht anhand der Antwortzeit erraten kann. Stimmt es nicht überein, endet der Ablauf sofort mit HTTP 401 — es passiert nichts weiter.

### Schritt 3 — Auftrag (Job) wird angelegt (wo: eZEUS `api`-Container, in Postgres gespeichert)

Anhand der `event_id` wird geprüft, ob dieses Ereignis bereits bekannt ist (Schutz gegen doppelte Verarbeitung, z. B. wenn Paperless denselben Webhook zweimal sendet). Ist es neu, wird ein Datenbankeintrag für das Dokument (falls noch nicht vorhanden) sowie ein neuer **Job** mit Status `RECEIVED` angelegt.

### Schritt 4 — Job wird in die Warteschlange eingereiht (wo: Redis)

Der neue Job wird an die Warteschlange (Redis, verwaltet über Celery) übergeben, Status wechselt zu `QUEUED`. Der Webhook antwortet Paperless-ngx sofort mit HTTP 202 — die eigentliche Verarbeitung läuft danach **unabhängig und asynchron** weiter, Paperless muss nicht warten.

### Schritt 5 — Ein Worker übernimmt den Job (wo: eZEUS `worker`-Container)

Ein freier Worker-Prozess holt sich den Job aus der Warteschlange, Status wechselt zu `RUNNING`. Ab hier läuft die eigentliche Verarbeitung in klar getrennten, einzeln protokollierten Phasen:

**Phase A — Metadaten laden.** Der Worker fragt bei Paperless-ngx per `GET /api/documents/128/` die aktuellen Metadaten ab (Dateiname, Dokumenttyp, MIME-Type).

**Phase B — Datei herunterladen.** Per `GET /api/documents/128/download/` wird die eigentliche Datei geladen und temporär auf dem eZEUS-Server gespeichert. Ist die Datei größer als `MAX_DOCUMENT_BYTES`, bricht der Job an dieser Stelle kontrolliert ab.

**Phase C — Texterkennung (OCR).** Die Datei wird an PaddleOCR übergeben, das den kompletten Text der Seite(n) erkennt — vergleichbar mit dem, was beim Scannen eines Dokuments automatisch passiert. Ergebnis: reiner Text, noch keine strukturierten Felder.

**Phase D — OCR-Text zurückschreiben.** Der erkannte Text wird nach Paperless-ngx zurückgeschrieben, **aber nur, wenn das Textfeld dort noch leer ist**. Hat Paperless bereits selbst einen Text erkannt, bleibt dieser unangetastet.

**Phase E — passende Vorlage auswählen.** Anhand des Dokumenttyps (aus Phase A) sucht das System die dazu passende, aktive Standard-Vorlage (siehe Abschnitt 6). Gibt es keine passende Vorlage, endet der Job hier regulär — nicht als Fehler, sondern mit dem Hinweis „keine Extraktionsregeln vorhanden“.

**Phase F — Felder extrahieren (hier, und nur hier, kann KI beteiligt sein).** Für jedes in der Vorlage definierte Feld werden die konfigurierten Provider durchlaufen:
- `regex` — sucht nach einem festen Textmuster (z. B. „Rechnungsnummer: gefolgt von Zeichen“). Schnell, vorhersagbar, für gut strukturierte Dokumente ideal.
- `keyword` — sucht nach Schlüsselwörtern in der Nähe des gesuchten Wertes.
- `ollama` — **nur wenn `OLLAMA_ENABLED=true` und im Feld konfiguriert:** Der erkannte Text wird an ein lokales KI-Modell geschickt, das gezielt nach dem gesuchten Wert gefragt wird (mit fester, niedriger „Kreativität“, damit es keine Werte erfindet). Wird für Fälle genutzt, bei denen feste Muster nicht zuverlässig greifen, weil der Text zu variabel ist.

Jeder Provider liefert null, einen oder mehrere Kandidatenwerte mit einer Konfidenz (Vertrauenswert) zurück — alle werden zunächst nur gespeichert, noch nicht übernommen.

**Phase G — Kandidaten validieren.** Jeder Kandidat durchläuft die in der Vorlage hinterlegten Prüfungen (z. B. `monetary_amount` normalisiert „1.234,56 EUR“ zu „1234.56“; `date` prüft ein gültiges Datumsformat; `not_empty` verlangt einen nicht-leeren Wert). Liefern mehrere Provider für dasselbe Feld **unterschiedliche** Werte, wird bewusst **kein** Wert übernommen — das System rät nicht, sondern markiert den Konflikt.

**Phase H — aktuellen Stand erneut laden.** Direkt vor dem Schreiben holt der Worker den Dokumentenstand ein weiteres Mal von Paperless-ngx. Das verkleinert das Zeitfenster, in dem jemand anderes das Dokument zwischenzeitlich bearbeitet haben könnte.

**Phase I — Ergebnisse schreiben.** Nur Felder, die in Paperless-ngx **zu diesem Zeitpunkt noch leer** sind, werden mit den validierten Werten befüllt. Bereits vorhandene oder manuell eingetragene Werte werden nie überschrieben. Jede tatsächlich vorgenommene Änderung wird mit Alt- und Neuwert im Audit-Log festgehalten.

**Phase J — Abschluss.** Temporäre Dateien werden gelöscht, der Job-Status wechselt zu `COMPLETED` (oder `COMPLETED_WITH_WARNINGS`, falls z. B. keine Vorlage gefunden wurde). Tritt in irgendeiner Phase ein Fehler auf, wird nur diese Phase als `FAILED` markiert, der Job erhält Status `FAILED` mit Fehlerart und -meldung.

### Schritt 6 — Ergebnis ist sichtbar (wo: Paperless-ngx und eZEUS-Dashboard)

In Paperless-ngx erscheinen die neu gesetzten Felder wie gewohnt am Dokument. Im eZEUS-Dashboard (`/`) lässt sich der komplette Job inklusive aller Phasen, Zeiten und — bei Fehlern — der genauen Fehlermeldung einsehen.

### Konkretes Beispiel: Rechnungsbetrag

```
OCR-Rohtext:        "Gesamtbetrag: 1.234,56 EUR"
Regel (Provider):   regex sucht "Gesamtbetrag:\s*([\d.,]+\s*EUR)"
Roher Treffer:       "1.234,56 EUR"
Validator:           monetary_amount normalisiert → "1234.56"
Zielfeld in Paperless leer? → ja → Wert wird geschrieben
Audit-Log:            Feld "total", alt=leer, neu="1234.56"
```

Stünde im Zielfeld bereits ein Wert (z. B. weil jemand ihn von Hand eingetragen hat), würde in diesem letzten Schritt **nichts** geschrieben — der vorhandene Wert bleibt unverändert.

---

## 9. Fehlgeschlagene Jobs & Wiederholung

Fehlgeschlagene oder mit Warnungen abgeschlossene Jobs lassen sich über die Admin-API erneut anstoßen:

```bash
curl -X POST http://localhost:8080/api/jobs/<job-id>/retry \
  -H "X-EZEUS-Admin-Secret: <euer Admin-Secret>"
```

Automatische Wiederholungsversuche sind zusätzlich über `JOB_MAX_RETRIES` und `JOB_RETRY_DELAYS_SECONDS` steuerbar (z. B. 3 Versuche nach 30 s, 2 min, 10 min).

---

## 10. Bekannte Einschränkungen

- Aktuell nur eine Paperless-Instanz pro Deployment vorgesehen.
- Die Admin-API kennt nur ein gemeinsames Geheimnis, keine Benutzerrollen oder abgestufte Rechte.
- Es gibt noch keine mitgelieferte Vorlage für Lieferscheine oder andere Dokumenttypen außer dem Rechnungs-Beispiel — eigene Vorlagen müssen selbst angelegt werden (siehe Abschnitt 6).
- Laut Projektstand kein vollständiger Lasttest und keine fertige Referenzdatensynchronisation — für den produktiven Einsatz vor dem Rollout selbst prüfen.
