# Betriebsdashboard und Logs

eZEUS-AI-2 liefert am Startpfad `/` ein schlankes Betriebsdashboard aus. Es
benötigt keine zusätzliche Frontend-Laufzeit und wird direkt von FastAPI
bereitgestellt.

## Navigation

- `Übersicht`: Betriebszustand und konfigurierte lokale Komponenten
- `Logs`: aktuelle Phasen der Dokumentenverarbeitung
- `API`: FastAPI-/OpenAPI-Dokumentation unter `/docs`

## Verarbeitungsprotokoll

Das Protokoll zeigt höchstens 50 Einträge pro Seite. **Vorherige Seite** und
**Nächste Seite** ersetzen die sichtbaren Zeilen, statt weitere Einträge unter
die bestehende Tabelle zu hängen. Die Seitenanzeige nennt den sichtbaren
Bereich und die Gesamtzahl der Treffer. Instanz und Suchtext bilden gemeinsam
den aktiven Filter. Die gewählte Instanz wird im Browser gespeichert und schon
beim ersten Abruf verwendet. Existiert sie später nicht mehr, fällt die Ansicht
mit einem Hinweis auf **Alle Instanzen** zurück.

Jede Zeile besitzt eine Auswahlbox. Die Kopfauswahl markiert ausschließlich die
aktuelle Seite mit höchstens 50 Einträgen;
anschließend kann die Auswahl auf alle Treffer des aktiven Filters erweitert
werden, auch wenn diese noch nicht nachgeladen wurden. Laufende oder wartende
Aufträge bleiben deaktiviert. Nach dem Löschen nennt die Statuszeile die Zahl
der gelöschten und übersprungenen Einträge. Auswahl und aufgeklappte Details
bleiben bei automatischer Aktualisierung erhalten; ein Seiten- oder
Filterwechsel leert die Seitenauswahl.

Status und Verarbeitungsschritte erscheinen mit festen deutschen Bezeichnungen.
Fehler werden zur Anzeigezeit in **Was ist passiert**, **Warum**, **Was tun**
und einklappbare technische Details gegliedert. Diese Erklärungen gelten damit
auch für ältere Aufträge. Dokumentinhalt und Zugangsdaten werden ausgeblendet.

## Log-API

`GET /api/logs` liefert die neuesten Phasenereignisse aus der eZEUS-Datenbank.
Der Parameter `limit` akzeptiert Werte zwischen `1` und `500`; Standard ist
`50`. `instance_slug` und `q` filtern serverseitig; deutsche Status- und
Phasenbezeichnungen sind ebenfalls suchbar.

Beispiel:

```bash
curl "http://localhost:8080/api/logs?limit=50"
```

Ein Eintrag enthält nur:

- Job-ID
- externe Dokument-ID
- Dateiname
- Phase und Status mit deutschen Anzeigebezeichnungen
- Start- und Endzeit
- berechnete Laufzeit
- Fehlerklasse, falls eine Phase fehlgeschlagen ist

Nicht ausgegeben werden:

- Dokumentinhalt oder OCR-Text
- extrahierte Geschäftsdaten
- Tokens, Passwörter oder Webhook-Secrets
- OCR- oder sonstige Dokumentinhalte in Phase-Metadaten
- unbereinigte Fehlertexte oder Stacktraces

Die Browseroberfläche erzeugt Tabellenzellen ausschließlich über `textContent`.
Werte aus Dateinamen oder Datenbankfeldern werden nicht als HTML interpretiert.

## Löschen und Zugriffsschutz

`POST /api/logs/delete` akzeptiert bis zu 500 Job-IDs. Mit
`POST /api/logs/delete-matching` werden alle Treffer des angegebenen Instanz-
und Suchfilters erfasst. Beide Endpunkte benötigen Administratorrechte,
schreiben genau einen Audit-Eintrag pro Aufruf und löschen nur Endstatus. Die
Antwort enthält `deleted` und `skipped`. Der ältere Einzelendpunkt
`DELETE /api/logs/{job_id}` bleibt verfügbar.

Geschützte Verwaltungsbereiche verwenden die persönlichen eZEUS-Konten mit
rollenbasierter Berechtigung. Der Reverse-Proxy terminiert TLS, darf aber keine
zusätzliche HTTP-Basic-Authentication vor die Browseroberfläche schalten. So
entsteht kein zweites, browserseitiges Passwortfenster neben der eZEUS-Anmeldung.
Der Host-Port ist beim Compose-Betrieb standardmäßig nur an Loopback gebunden.

Das Kubernetes-Chart kann für zentrale Installationen optional
oauth2-proxy/OIDC per ingress-nginx `auth_request` verwenden; nur Webhook und
`/health` bleiben dabei öffentlich.

Beispielwerte:

```nginx
server {
    listen 443 ssl;
    server_name ezeus.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

Die Beispieldomain und Pfade sind Platzhalter. Sie enthalten keine Angaben zu
einer konkreten Installation. Eine vorgeschaltete Browser-Basic-Auth ist
absichtlich nicht Teil dieses Beispiels.
