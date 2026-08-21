# eZEUS-AI-2

eZEUS-AI-2 ist eine automatisierte Verarbeitungspipeline für [Paperless-ngx](https://docs.paperless-ngx.com/). Sobald in Paperless ein neues Dokument auftaucht, liest eZEUS den von Paperless bereits erkannten Text, extrahiert einzelne Felder (z. B. Rechnungsnummer, Betrag, Datum) anhand konfigurierbarer Regeln oder optional per lokalem KI-Modell, validiert die Ergebnisse und schreibt sie zurück nach Paperless — ohne jemals vorhandene oder manuell gesetzte Werte zu überschreiben. Die Texterkennung (OCR) übernimmt vollständig Paperless-ngx; eZEUS führt keine eigene OCR durch.

Alles läuft lokal (eigener Server, eigenes Docker-Netz). Es gibt standardmäßig keine Verbindung zu Cloud-Diensten.

> **Hinweis zum Modellstandort (Stand 03.08.2026):** Das produktiv verwendete
> Sprachmodell `qwen3:4b` läuft in einem eigenen Ollama-Container auf dem
> Server, **nicht** auf einem Windows-PC. `OLLAMA_BASE_URL` zeigt auf den
> Docker-Service `ollama` im privaten Server-Netz (`http://ollama:11434`) –
> das ist keine PC-Adresse. Eine Umstellung auf PC-Inferenz wäre ein eigener
> Architektur- und Sicherheitsumbau (gesicherter Netzwerkkanal, authentifizierte
> Modell-API, Firewallregeln) und ist aktuell nicht umgesetzt.

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
11. [Mehrere Paperless-Instanzen (Mandantenfähigkeit)](#11-mehrere-paperless-instanzen-mandantenfähigkeit)
12. [Projektstruktur](#12-projektstruktur)
13. [Tests](#13-tests)
14. [Fehlerbehebung](#14-fehlerbehebung)
15. [Sicherheitshinweise](#15-sicherheitshinweise)
16. [Backup und Wiederherstellung](#16-backup-und-wiederherstellung)
17. [Entwicklung und Erweiterung](#17-entwicklung-und-erweiterung)
18. [Lizenz](#18-lizenz)

---

## 1. Voraussetzungen

| Komponente | Version / Hinweis |
|---|---|
| Docker + Docker Compose | aktuelle Version, Compose v2 |
| Alternativ: Kubernetes + Helm | Kubernetes ab 1.26 und Helm 4 (Chart wird mit Helm 4.2 geprüft) |
| Laufende Paperless-ngx-Instanz | erreichbar per HTTP(S) vom eZEUS-Server aus |
| Paperless API-Token | wird unter Paperless → Einstellungen → API-Token erzeugt |
| Freier Arbeitsspeicher | mind. 2 GB (optional mehr, wenn Ollama aktiviert ist) |
| Optional: NVIDIA-GPU | nur nötig, wenn Ollama auf GPU statt CPU laufen soll |

eZEUS bringt in seiner `docker-compose.yml` **keine echte Paperless-Instanz** mit — dort läuft standardmäßig nur ein *Mock-Paperless* für Tests/Entwicklung. Für den echten Betrieb zeigt eZEUS auf eure bestehende Paperless-ngx-Installation (per `PAPERLESS_BASE_URL`, siehe Abschnitt 4).

---

## 2. Aufbau des Systems

eZEUS besteht aus mehreren Containern, die zusammenspielen:

```
                         ┌─────────────────────┐
   Paperless-ngx  ─────► │   api (FastAPI)      │  nimmt Webhooks entgegen,
   (Webhook bei          │   Port 8080          │  stellt Admin-API & Dashboard
   neuem Dokument)       └──────────┬───────────┘  bereit
                                    │ speichert Job + Outbox
                                    ▼
                          ┌──────────────────┐
                          │   postgres        │  Job + Queue-Outbox werden
                          │                   │  atomar gespeichert
                          └──────────┬────────┘
                                    │
                                    ▼
                          ┌──────────────────┐
                          │   outbox          │  übergibt dauerhaft gespeicherte
                          │                   │  Jobs an Redis/Celery
                          └──────────┬────────┘
                                    │
                                    ▼
                          ┌──────────────────┐
                          │   redis           │  Warteschlange (Queue)
                          └──────────┬────────┘
                                    │
                                    ▼
                          ┌──────────────────┐       ┌─────────────────┐
                          │   worker (Celery) │──────►│  Paperless-ngx   │
                          │   Extraktion      │       │  (Text lesen,    │
                          │   + Validierung   │◄──────│   Werte schreiben)│
                          └──────────┬────────┘       └─────────────────┘
                                    │
                                    └────────────► PostgreSQL speichert außerdem
                                                   Templates, Ergebnisse und Audit-Log

                          (optional, nur wenn aktiviert)
                          ┌──────────────────┐
                          │   ollama          │  lokales KI-Modell für
                          │                   │  komplexere Extraktionsfälle
                          └──────────────────┘
```

**Wichtig:** Die `api` nimmt den Webhook nur entgegen und speichert Job plus Queue-Outbox in einer gemeinsamen Datenbanktransaktion. Der `outbox`-Dienst veröffentlicht den Auftrag wiederholbar an Redis. Die eigentliche Verarbeitung passiert **komplett getrennt** im `worker`-Container. Ein vorübergehender Redis-Ausfall kann dadurch keinen bereits bestätigten Job verlieren.

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

> Alle produktiven Secrets müssen sich vom Beispielwert unterscheiden. Startet eZEUS mit `APP_ENV=production` und einem noch unveränderten Beispiel-Secret, verweigert die Anwendung absichtlich den Start (Sicherheitsmaßnahme).

### 3.3 Container bauen und starten

```bash
docker compose build
docker compose up -d
```

Das startet: `api`, `worker`, `outbox`, `postgres`, `redis` (und im Standard-Compose-File zusätzlich ein Mock-Paperless für Testzwecke). Kein gesondertes OCR-Image nötig — API, Worker und Outbox verwenden dasselbe gehärtete Non-Root-Image.

### 3.4 Datenbank-Migrationen

Die Migrationen laufen beim Start des `api`-Containers automatisch und werden bei PostgreSQL durch ein Advisory Lock serialisiert. Manuell nachziehen, falls nötig:

```bash
docker compose exec api python -m core.db.migrate
```

Danach das erste persönliche Administratorkonto interaktiv anlegen:

```bash
docker compose exec api python -m scripts.create_admin_user <benutzername>
```

### 3.5 Health-Check

```bash
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

`/ready` prüft zusätzlich Datenbank, Redis, Paperless-Erreichbarkeit und — falls aktiviert — Ollama. Erst wenn hier alles `true` zurückgibt, ist das System vollständig betriebsbereit.

### 3.6 Kubernetes / Helm

Das produktionsnahe Helm-Chart liegt unter `deploy/helm/ezeus-ai-2`. Es enthält API, Worker, transaktionalen Outbox-Dispatcher, Migrationen, PostgreSQL, Redis, optional Ollama, HPA/PDB, NetworkPolicies, Ingress und optionalen OIDC-Schutz über oauth2-proxy.

```bash
docker build --tag registry.example/ezeus-ai-2:0.2.0 .
docker push registry.example/ezeus-ai-2:0.2.0
cp deploy/helm/ezeus-ai-2/values-production.example.yaml values-production.yaml
# Image-Registry, Hosts, CIDRs und existingSecret in values-production.yaml ersetzen
helm upgrade --install ezeus deploy/helm/ezeus-ai-2 \
  --namespace ezeus --create-namespace \
  --values values-production.yaml \
  --wait --timeout 10m
```

Produktive Secrets gehören in ein vorhandenes Sealed/External Secret; sie dürfen nicht in der Values-Datei stehen. Die vollständige Anleitung und das Schlüsselschema stehen in [der Helm-Dokumentation](deploy/helm/ezeus-ai-2/README.md).

---

## 4. Konfiguration (.env)

| Variable | Bedeutung |
|---|---|
| `APP_ENV` | `development` oder `production`. In `production` werden Beispiel-Secrets abgelehnt. |
| `APP_HOST` / `APP_PORT` | Bind-Adresse der API (Standard `0.0.0.0:8080`) |
| `APP_LOG_LEVEL` | Log-Level, z. B. `INFO` |
| `FORWARDED_ALLOW_IPS` | Vertrauenswürdige Reverse-Proxy-Adressen; im Helm-Cluster `*`, da NetworkPolicies den Service abschirmen |
| `POSTGRES_PASSWORD` | Passwort für die interne Datenbank |
| `DATABASE_URL` | Vollständige DB-Verbindung (muss zum Passwort passen) |
| `REDIS_URL` | Verbindung zur Warteschlange |
| `PAPERLESS_BASE_URL` | URL eurer Paperless-ngx-Instanz, z. B. `https://paperless.meinefirma.local` |
| `PAPERLESS_API_TOKEN` | API-Token aus Paperless (zum Lesen/Schreiben von Dokumenten) |
| `PAPERLESS_WEBHOOK_SECRET` | Gemeinsames Geheimnis, das Paperless bei jedem Webhook-Aufruf mitschickt |
| `PAPERLESS_VERIFY_TLS` | TLS-Zertifikatsprüfung bei HTTPS-Verbindung zu Paperless |
| `PROXY_AUTH_SECRET` | Optionales internes Secret für einen vertrauenswürdigen Authentifizierungs-Proxy |
| `LOCAL_ONLY` | Wenn `true`: keine Cloud-KI-Anbindung möglich, egal was sonst konfiguriert ist |
| `CLOUD_AI_GLOBALLY_ALLOWED` | Muss `false` bleiben, solange `LOCAL_ONLY=true` — sonst verweigert die Anwendung den Start |
| `OLLAMA_ENABLED` | Schaltet die lokale KI-Extraktion frei (`true`/`false`) |
| `OLLAMA_BASE_URL` | Adresse des Ollama-Dienstes |
| `OLLAMA_MODEL` | Modellname, z. B. `qwen3:4b` |
| `OLLAMA_TIMEOUT_SECONDS` | Maximale Wartezeit auf eine KI-Antwort |
| `OLLAMA_MAX_INPUT_CHARS` | Wie viel Dokumenttext maximal an das Modell geschickt wird (längerer Text wird gekürzt) |
| `OLLAMA_MAX_RESPONSE_BYTES` | Harte maximale Antwortgröße von Ollama |
| `JOB_MAX_RETRIES` | Wie oft ein fehlgeschlagener Job automatisch wiederholt wird |
| `JOB_RETRY_DELAYS_SECONDS` | Wartezeiten zwischen den Wiederholungsversuchen, z. B. `30,120,600` |
| `CELERY_CONCURRENCY` | Worker-Prozesse je Compose-Container (Standard `2`) |
| `RATE_LIMIT_*` | Anwendungslimiter; im Helm-Deployment zusätzlich ingress-nginx-Limits |
| `OUTBOUND_ALLOWED_HOSTS` | Optionale feste Host-Allowlist; sobald gesetzt, ist sie auch für verwaltete Instanzen verbindlich |
| `OUTBOUND_PRIVATE_ALLOWED_HOSTS` | Explizite Ausnahme für interne FQDNs; allowlist-geprüfte Kubernetes-Kurznamen dürfen ClusterIPs nutzen, Loopback/Link-Local bleiben gesperrt |
| `PAPERLESS_MAX_DOWNLOAD_BYTES` / `PAPERLESS_MAX_TEXT_CHARS` | Harte Streaming- und OCR-Textgrenzen |
| `REGEX_HARD_TIMEOUT_SECONDS` | Echte Zeitunterbrechung pro regulärem Ausdruck |
| `OUTBOX_*` | Polling-, Claim- und Backoff-Grenzen des Queue-Outbox-Dispatchers |

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

Eine Vorlage legt fest, welche Felder aus welchem Dokumenttyp wie extrahiert und geprüft werden. Angelegt wird sie mit einem persönlichen Administratorkonto über die Admin-API:

```bash
curl -X POST http://localhost:8080/api/templates \
  -H "X-EZEUS-Admin-User: <benutzername>" \
  -H "X-EZEUS-Admin-Password: <passwort>" \
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
| `GET /ready` | Prüft Datenbank, Redis, Paperless-Erreichbarkeit und ggf. Ollama |
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

Anhand der `event_id` wird geprüft, ob dieses Ereignis bereits bekannt ist (Schutz gegen doppelte Verarbeitung). Ist es neu, werden Dokument, **Job** und Queue-Outbox atomar in PostgreSQL gespeichert; der Job erhält Status `QUEUED`.

### Schritt 4 — Job wird in die Warteschlange eingereiht (wo: Redis)

Der Outbox-Dispatcher übergibt den dauerhaft gespeicherten Job an Redis/Celery. Scheitert Redis vorübergehend, bleibt das Ereignis mit Backoff in PostgreSQL und wird erneut veröffentlicht. Der Webhook antwortet Paperless-ngx sofort mit HTTP 202 — die Verarbeitung läuft danach unabhängig weiter.

### Schritt 5 — Ein Worker übernimmt den Job (wo: eZEUS `worker`-Container)

Ein freier Worker-Prozess holt sich den Job aus der Warteschlange, Status wechselt zu `RUNNING`. Ab hier läuft die eigentliche Verarbeitung in klar getrennten, einzeln protokollierten Phasen:

**Phase A — Dokument laden (`LOAD_DOCUMENT`).** Der Worker fragt bei Paperless-ngx per `GET /api/documents/128/` Metadaten und den bereits erkannten OCR-Text ab. MIME-Typ, Antwortgröße und Textlänge werden begrenzt; eine Originaldatei wird nicht geladen.

**Phase B — Text lesen (`READ_DOCUMENT_TEXT`).** Vorhandener Paperless-Text wird direkt als Extraktionsgrundlage verwendet. Ist er leer, läuft der sichere Ablauf mit leerer Textquelle weiter und endet wegen fehlender Pflichtfelder mit Warnhinweis. Eigene Download-, OCR- oder OCR-Schreibphasen existieren nicht mehr.

**Phase C — passende Konfiguration auswählen (`SELECT_TEMPLATE`).** Für verwaltete Instanzen wird die aktive Feldkonfiguration geladen; andernfalls werden Paperless-Custom-Fields oder eine passende Templateversion verwendet. Fehlt jede Konfiguration, endet der Job regulär mit Warnhinweis.

**Phase D — Felder extrahieren (`EXTRACT_FIELDS`; hier, und nur hier, kann KI beteiligt sein).** Für jedes konfigurierte Feld werden die Provider durchlaufen:
- `regex` — sucht nach einem festen Textmuster (z. B. „Rechnungsnummer: gefolgt von Zeichen“). Schnell, vorhersagbar, für gut strukturierte Dokumente ideal.
- `keyword` — sucht nach Schlüsselwörtern in der Nähe des gesuchten Wertes.
- `ollama` — **nur wenn `OLLAMA_ENABLED=true` und im Feld konfiguriert:** Der erkannte Text wird an ein lokales KI-Modell geschickt, das gezielt nach dem gesuchten Wert gefragt wird (mit fester, niedriger „Kreativität“, damit es keine Werte erfindet). Wird für Fälle genutzt, bei denen feste Muster nicht zuverlässig greifen, weil der Text zu variabel ist.

Jeder Provider liefert null, einen oder mehrere Kandidatenwerte mit einer Konfidenz (Vertrauenswert) zurück — alle werden zunächst nur gespeichert, noch nicht übernommen.

**Phase E — Kandidaten validieren (`VALIDATE_RESULTS`).** Jeder Kandidat durchläuft die hinterlegten Prüfungen (z. B. `monetary_amount` normalisiert „1.234,56 EUR“ zu „1234.56“; `date` prüft ein gültiges Datumsformat; `not_empty` verlangt einen nicht-leeren Wert). Liefern mehrere Provider für dasselbe Feld **unterschiedliche** Werte, wird bewusst **kein** Wert übernommen — das System rät nicht, sondern markiert den Konflikt.

**Phase F — aktuellen Stand erneut laden (`RELOAD_METADATA`).** Direkt vor dem Schreiben holt der Worker den Dokumentenstand ein weiteres Mal von Paperless-ngx. Das verkleinert das Zeitfenster, in dem jemand anderes das Dokument zwischenzeitlich bearbeitet haben könnte.

**Phase G — Ergebnisse schreiben (`WRITE_METADATA`).** Nur Felder, die in Paperless-ngx **zu diesem Zeitpunkt noch leer** sind, werden mit den validierten Werten befüllt. Bereits vorhandene oder manuell eingetragene Werte werden nie überschrieben. Titel und Korrespondent werden nur nach den dafür geltenden Regeln gesetzt. Jede tatsächlich vorgenommene Änderung wird mit Alt- und Neuwert im Audit-Log festgehalten.

**Phase H — Aufräumen und Abschluss (`CLEANUP`, `COMPLETE`).** Der Job-Status wechselt zu `COMPLETED` oder `COMPLETED_WITH_WARNINGS`. Tritt in irgendeiner Phase ein Fehler auf, wird die aktive Phase als `FAILED` markiert; der Job erhält Status `FAILED` mit redigierter Fehlerart und -meldung.

### Schritt 6 — Ergebnis ist sichtbar (wo: Paperless-ngx und eZEUS-Dashboard)

In Paperless-ngx erscheinen die neu gesetzten Felder wie gewohnt am Dokument. Im eZEUS-Dashboard (`/`) lässt sich der komplette Job inklusive aller Phasen, Zeiten und — bei Fehlern — der genauen Fehlermeldung einsehen.

### Konkretes Beispiel: Rechnungsbetrag

```
Paperless-Text:     "Gesamtbetrag: 1.234,56 EUR"
Regel (Provider):   regex sucht "Gesamtbetrag:\s*([\d.,]+\s*EUR)"
Roher Treffer:      "1.234,56 EUR"
Validator:          monetary_amount normalisiert → "1234.56"
Zielfeld in Paperless leer? → ja → Wert wird geschrieben
Audit-Log:          Feld "total", alt=leer, neu="1234.56"
```

Stünde im Zielfeld bereits ein Wert (z. B. weil jemand ihn von Hand eingetragen hat), würde in diesem letzten Schritt **nichts** geschrieben — der vorhandene Wert bleibt unverändert.

---

## 9. Fehlgeschlagene Jobs & Wiederholung

Fehlgeschlagene oder mit Warnungen abgeschlossene Jobs lassen sich über die Admin-API erneut anstoßen:

```bash
curl -X POST http://localhost:8080/api/jobs/<job-id>/retry \
  -H "X-EZEUS-Admin-User: <benutzername>" \
  -H "X-EZEUS-Admin-Password: <passwort>"
```

Automatische Wiederholungsversuche sind zusätzlich über `JOB_MAX_RETRIES` und `JOB_RETRY_DELAYS_SECONDS` steuerbar (z. B. 3 Versuche nach 30 s, 2 min, 10 min).

---

## 10. Bekannte Einschränkungen

- Es gibt noch keine mitgelieferte Vorlage für Lieferscheine oder andere Dokumenttypen außer dem Rechnungs-Beispiel — eigene Vorlagen müssen selbst angelegt werden (siehe Abschnitt 6).
- Dashboard, Log-API und OpenAPI benötigen am Netzrand Authentifizierung. Das Helm-Chart liefert dafür optional oauth2-proxy/OIDC; bei Compose muss ein entsprechender TLS-Reverse-Proxy vorgeschaltet werden.
- Das Dashboard zeigt den konfigurierten Modellnamen. Das beweist weder den physischen Standort des Modells noch, dass es gerade geladen ist oder für den letzten Job verwendet wurde.
- Liefert Paperless-ngx keinen OCR-Text (z. B. bei Bilddateien ohne OCR-Konfiguration), findet eZEUS keine Felder und schließt den Job mit Warnhinweis ab.
- Ein belastbarer Last-/Kapazitätstest mit der konkreten Clustergröße bleibt Betreiberaufgabe.
- eZEUS lädt oder parst keine Dokumentbinärdateien mehr. Malware- und PDF-Bomb-Prüfung der Originaldatei liegt daher bei Paperless-ngx; eZEUS begrenzt den übernommenen MIME-Typ und OCR-Text sowie Containerressourcen.


---

## 11. Mehrere Paperless-Instanzen (Mandantenfähigkeit)

eZEUS kann mehrere Paperless-ngx-Installationen gleichzeitig bedienen. Jede angelegte Instanz ist ein eigener "Mandant" mit eigener Feldkonfiguration, eigenem Webhook und eigenem API-Token.

- Instanzen werden unter `/admin/instances` verwaltet (Name, Paperless-URL, API-Token und Webhook-Secret genügen zum Anlegen).
- Beim Anlegen prüft eZEUS die Verbindung und richtet in Paperless-ngx automatisch einen verwalteten Workflow ein, der neue und geänderte Dokumente an die richtige, instanzspezifische Webhook-URL meldet:

  ```
  https://<ezeus-host>/webhooks/paperless/<instanzkennung>
  ```

- Jede Instanz erhält automatisch die Standardfelder Korrespondent, Rechnungsnummer, Rechnungsdatum, Rechnungsbetrag, Kundennummer und Baustellennummer. Diese lassen sich unter „Feldkonfiguration“ pro Instanz anpassen (Bezeichnung, Typ, Pflichtstatus, Regex-/Keyword-/KI-Auslesung).
- Vorhandene Paperless-Custom-Fields werden beim Öffnen der Feldkonfiguration übernommen; neue Felder werden automatisch mit passendem Datentyp in Paperless angelegt und dauerhaft verknüpft.
- Zugriff erfolgt über persönliche Admin- bzw. Viewer-Konten (`/api/admin-users/page`). Die Rolle `admin` darf ändern, `viewer` darf nur lesen.
- Der bisherige globale Webhook (`/webhooks/paperless`, ohne Instanzkennung) bleibt für eine einzelne, über `.env` konfigurierte Instanz rückwärtskompatibel.

### Workflow manuell in Paperless anlegen

Der automatische Workflow (Button „Workflow einrichten“) ist optional. Wer den
Workflow lieber selbst in Paperless-ngx pflegt, legt dort eine Webhook-Aktion
mit exakt der oben gezeigten instanzspezifischen URL an. Dabei unbedingt
beachten:

- **Nur den Trigger „Dokument hinzugefügt“ verwenden, nicht „Dokument
  geändert“.** eZEUS schreibt erkannte Felder per API nach Paperless zurück —
  das zählt selbst als Änderung. Ein Workflow, der auch auf „Dokument
  geändert“ reagiert, löst sich dadurch bei jedem Durchlauf selbst erneut aus
  und kann eine Endlosschleife aus Webhook-Aufrufen erzeugen (in einem
  Vorfall führte das zu 66 Webhook-Aufrufen über 14 Dokumente aus einem
  einzigen Testupload, bis Paperless mit HTTP-500-Fehlern reagierte).
- Der Webhook-Body muss `document_id` enthalten (bei Paperless-ngx als
  Template-Platzhalter aus der Dokument-URL ableitbar, siehe
  `connectors/paperless/connector.py`), sowie den Header
  `X-EZEUS-Webhook-Secret` mit dem in eZEUS hinterlegten Secret dieser
  Instanz.

„Verbindung testen“ prüft neben der reinen Paperless-Erreichbarkeit
inzwischen auch, ob in Paperless ein aktivierter Workflow mit einer
Webhook-Aktion existiert, deren Ziel-URL exakt auf die eZEUS-Webhook-Adresse
dieser Instanz zeigt — unabhängig davon, ob der Workflow automatisch oder von
Hand angelegt wurde. Meldungen:

- „kein Workflow gefunden“ — keine passende Webhook-URL in Paperless
  konfiguriert.
- „Workflow … gefunden, aber: …“ — Workflow existiert, ist aber deaktiviert
  und/oder reagiert zusätzlich auf „Dokument geändert“ (Endlosschleifen-Gefahr,
  siehe oben).
- „Workflow … korrekt eingerichtet“ — Webhook ist funktionsfähig verdrahtet.

Der Test verändert dabei nichts in Paperless; das Anlegen/Reparieren bleibt
dem Button „Workflow einrichten“ bzw. der manuellen Pflege vorbehalten.

## 12. Projektstruktur

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
- `core/queue`: Celery-Konfiguration, Queue-Adapter und transaktionaler Outbox-Dispatcher
- `core/templates`: Template-Schema und Auswahl
- `core/validation`: Validierungs- und Normalisierungslogik
- `plugins`: Extraktions-, LLM- und Validierungsbausteine
- `webhooks`: Paperless-Webhook, Schema und Secret-Prüfung
- `infrastructure/migrations`: Alembic-Konfiguration und Migrationen
- `scripts`: Hilfsskripte und echter Container-Smoke-Test
- `deploy/helm/ezeus-ai-2`: Kubernetes-/Helm-Deployment
- `tests`: Unit-, API- und Integrationstests
- `docs`: ergänzende Architektur-, Betriebs- und Sicherheitsdokumentation

Die API startet über `apps.api.main:app`. Celery lädt `core.queue.celery_app:celery_app`. Der Entwicklungs-Mock startet über `apps.mock_paperless.main:app`.

## 13. Tests

Vollständige Tests:

```bash
make test
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
make container-smoke
make smoke-down
make helm-check
```

Weitere Informationen stehen in [docs/testing.md](docs/testing.md).

## 14. Fehlerbehebung

- `/health` antwortet, `/ready` liefert aber HTTP 503: Die Antwort enthält den Status von Datenbank, Redis, Paperless und gegebenenfalls Ollama.
- Paperless meldet HTTP 401: `PAPERLESS_API_TOKEN` und `PAPERLESS_BASE_URL` prüfen.
- Der Webhook meldet HTTP 401: Header und `PAPERLESS_WEBHOOK_SECRET` müssen übereinstimmen.
- Administrative Endpunkte melden HTTP 401: mit einem aktiven persönlichen Konto über die Verwaltungsoberfläche oder die Header `X-EZEUS-Admin-User` und `X-EZEUS-Admin-Password` anmelden. Falls noch kein Konto existiert, eines mit `python -m scripts.create_admin_user <benutzername>` anlegen.
- Job endet mit Warnhinweis, Felder fehlen: Paperless hat keinen OCR-Text zum Dokument gespeichert — sicherstellen, dass Paperless-ngx OCR aktiviert hat und das Dokument korrekt verarbeitet wurde.
- Das Ollama-Modell wird nicht als bereit erkannt: `OLLAMA_ENABLED`, `OLLAMA_BASE_URL` und `OLLAMA_MODEL` prüfen.
- Portänderungen: `APP_PORT` in `.env` setzen und den Compose-Stack neu erstellen.
- Ein einzelnes Dokument erzeugt auffällig viele Jobs/Webhook-Aufrufe
  hintereinander: sehr wahrscheinlich reagiert der Paperless-Workflow dieser
  Instanz zusätzlich auf „Dokument geändert“ und löst sich durch eZEUS'
  eigenes Zurückschreiben der Felder selbst erneut aus. „Verbindung testen“
  unter Abschnitt 11 zeigt diese Fehlkonfiguration an; Trigger in Paperless
  auf „Dokument hinzugefügt“ beschränken.

## 15. Sicherheitshinweise

- `.env` und lokale Varianten sind durch `.gitignore` ausgeschlossen.
- Reale Tokens, Passwörter und Schlüssel dürfen nicht versioniert oder in Images eingebettet werden.
- TLS-Prüfung für Paperless ist standardmäßig aktiv.
- Dashboard, Log-Endpunkt und OpenAPI werden im Helm-Deployment über den optionalen oauth2-proxy/OIDC-Ingress geschützt. Bei Compose ist ein authentifizierender TLS-Reverse-Proxy erforderlich.
- Administrationskonten verwenden Scrypt-Passworthashes und die Rollen `admin` und `viewer`. Es gibt keinen gemeinsamen Bootstrap-Schlüssel in der HTTP-API.
- Der Paperless-Mock ist ausschließlich für lokale Entwicklung und Tests vorgesehen.
- Container-Netze, Datenbank und Redis dürfen im Produktivbetrieb nicht öffentlich erreichbar sein.
- Der Quellcode enthält keine produktiven Zugangsdaten. Die Werte in `.env.example` sind erkennbare Platzhalter.
- Ausgehende Paperless-/Ollama-Aufrufe verwenden Host-Allowlisting, DNS-/Privatnetzschutz und harte Streaming-Grenzen.
- CI prüft Lockfiles, Tests, Ruff, mypy, Bandit, `pip-audit`, Helm/kubeconform, Gitleaks, Trivy und einen realen Compose-Workflow.

Die umgesetzten Schutzmaßnahmen und verbleibenden Betreiberpflichten stehen in [docs/security.md](docs/security.md); der historische Bericht samt Auflösungsmatrix steht in [CODE_REVIEW_REPORT.md](CODE_REVIEW_REPORT.md).

## 16. Backup und Wiederherstellung

PostgreSQL enthält die dauerhaften Aufträge, Templates, Ergebnisse und Auditdaten. Vor einem Backup sollten API und Worker keine neuen Aufträge annehmen.

Beispiel für ein PostgreSQL-Backup:

```bash
docker compose exec -T postgres pg_dump -U ezeus -d ezeus -Fc > ezeus.dump
```

Beispiel für die Wiederherstellung:

```bash
docker compose exec -T postgres pg_restore -U ezeus -d ezeus --clean --if-exists < ezeus.dump
```

Die lokale `.env`-Datei muss getrennt und verschlüsselt gesichert werden. Das Redis-Volume enthält Warteschlangen- und Ergebniszustand, ist aber nicht die führende fachliche Datenquelle.

Eine Wiederherstellung muss zunächst in einer getrennten Umgebung getestet werden.

## 17. Entwicklung und Erweiterung

- Neue Extraktionsprovider implementieren `ExtractionProvider` aus `plugins/base/interfaces.py`.
- Neue Template-Provider und Validatornamen müssen in `core/templates/schema.py` freigegeben werden.
- Datenbankänderungen benötigen eine Alembic-Migration.
- Änderungen an Connectoren müssen den Schutz bereits gefüllter Paperless-Felder erhalten.
- Vor jeder Übernahme müssen Tests, Ruff, Formatter und mypy erfolgreich ausgeführt werden.

## 18. Lizenz

Das Projekt ist derzeit proprietär/source-available. Die Datei [LICENSE](LICENSE) räumt ohne vorherige schriftliche Genehmigung keine Nutzungs-, Änderungs- oder Weitergaberechte ein. Drittanbieter-Komponenten behalten ihre jeweiligen Lizenzen.
