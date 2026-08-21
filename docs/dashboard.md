# Betriebsdashboard und Logs

eZEUS-AI-2 liefert am Startpfad `/` ein schlankes Betriebsdashboard aus. Es
benötigt keine zusätzliche Frontend-Laufzeit und wird direkt von FastAPI
bereitgestellt.

## Navigation

- `Übersicht`: Betriebszustand und konfigurierte lokale Komponenten
- `Logs`: aktuelle Phasen der Dokumentenverarbeitung
- `API`: FastAPI-/OpenAPI-Dokumentation unter `/docs`

## Log-API

`GET /api/logs` liefert die neuesten Phasenereignisse aus der eZEUS-Datenbank.
Der Parameter `limit` akzeptiert Werte zwischen `1` und `250`; Standard ist
`100`.

Beispiel:

```bash
curl "http://localhost:8080/api/logs?limit=50"
```

Ein Eintrag enthält nur:

- Job-ID
- externe Dokument-ID
- Dateiname
- Phase und Status
- Start- und Endzeit
- berechnete Laufzeit
- Fehlerklasse, falls eine Phase fehlgeschlagen ist

Nicht ausgegeben werden:

- Dokumentinhalt oder OCR-Text
- extrahierte Geschäftsdaten
- Tokens, Passwörter oder Webhook-Secrets
- interne Phase-Metadaten
- vollständige Fehlertexte oder Stacktraces

Die Browseroberfläche erzeugt Tabellenzellen ausschließlich über `textContent`.
Werte aus Dateinamen oder Datenbankfeldern werden nicht als HTML interpretiert.

## Zugriffsschutz

Die Anwendung erzwingt für das reine Betriebsdashboard keine eigene Anmeldung.
Das Kubernetes-Chart kann deshalb oauth2-proxy/OIDC per ingress-nginx
`auth_request` vorschalten; nur Webhook und `/health` bleiben öffentlich. Beim
Compose-Betrieb muss der gesamte Browserzugriff über einen authentifizierenden
TLS-Reverse-Proxy laufen. Der Host-Port ist standardmäßig nur an Loopback
gebunden.

Beispielwerte:

```nginx
server {
    listen 443 ssl;
    server_name ezeus.example.com;

    auth_basic "eZEUS";
    auth_basic_user_file /etc/nginx/.htpasswd-ezeus;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

Die Beispieldomain und Pfade sind Platzhalter. Sie enthalten keine Angaben zu
einer konkreten Installation.
