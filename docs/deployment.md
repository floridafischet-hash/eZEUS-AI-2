# Deployment

## Docker Compose

`docker compose up --build` erstellt API, Worker, Outbox-Dispatcher,
PostgreSQL, Redis und den Paperless-API-Mock. Der Mock dient ausschließlich
reproduzierbaren Entwicklungs- und Smoke-Tests. Im Produktivbetrieb setzt
`docker-compose.production.yml` `APP_ENV=production` verbindlich und liest die
echte `PAPERLESS_BASE_URL` aus `${EZEUS_ENV_FILE:-.env}`.

Das API-Startkommando führt `python -m core.db.migrate` aus. PostgreSQL-
Migrationen werden durch ein Advisory Lock serialisiert. Alle eZEUS-Dienste
laufen als nicht privilegierter Benutzer; veröffentlichte Entwicklungsports
sind an `127.0.0.1` gebunden.

Ein echter Container-Workflow lässt sich ausführen mit:

```bash
make container-smoke
make smoke-down
```

Der Test migriert eine echte PostgreSQL-Datenbank, prüft `/ready`, sendet einen
Webhook, verarbeitet ihn über Outbox, Redis und Celery und kontrolliert die
Rückschreibungen im Paperless-Mock.

## Kubernetes

Das Chart `deploy/helm/ezeus-ai-2` ist das vorgesehene produktive Deployment.
Es enthält:

- API, Worker und Outbox als getrennte Deployments
- PostgreSQL, Redis und optional Ollama als StatefulSets
- serialisierte Migrationen als Init-Container; optionaler Helm-Hook nur für
  bereits erreichbare externe Datenbanken
- HPA, PDB, Ressourcenlimits sowie gehärtete Pod-/Container-Security-Contexts
- NetworkPolicies mit explizitem internem und CIDR-basiertem externem Egress
- ingress-nginx-Rate-Limits und optional oauth2-proxy/OIDC
- PVCs beziehungsweise explizite `emptyDir`-Entwicklungsvarianten

Die mitgelieferten StatefulSets sind einzelne persistente Instanzen und kein
HA-Datenbank-/Redis-Cluster. Für Hochverfügbarkeit werden PostgreSQL und Redis
über `external.*` beziehungsweise ein `existingSecret` als gemanagte Dienste
angebunden.

Vor der Installation muss genau der geprüfte Stand versioniert in eine für den
Cluster erreichbare Registry gebaut werden; das Chart baut keine Images:

```bash
docker build --tag registry.example/ezeus-ai-2:0.2.0 .
docker push registry.example/ezeus-ai-2:0.2.0
```

`image.repository`, `image.tag` und gegebenenfalls `imagePullSecrets` werden in
der eigenen Produktions-Values-Datei auf diese Registry gesetzt.

```bash
helm upgrade --install ezeus deploy/helm/ezeus-ai-2 \
  --namespace ezeus --create-namespace \
  --values deploy/helm/ezeus-ai-2/values-production.example.yaml \
  --wait --timeout 10m
```

Die Beispieldatei muss vorher kopiert und angepasst werden. Insbesondere sind
Test-Domains, Egress-CIDRs und `existingSecret` installationsspezifisch zu
ersetzen. `make helm-check` führt Helm-Lint, zwei Renderings und eine strikte
kubeconform-Prüfung aus.

Das PostgreSQL-Advisory-Lock serialisiert Migrationsprozesse, macht alte Pods
aber nicht automatisch mit jeder destruktiven Schemaänderung kompatibel. Bei
solchen Upgrades werden eingehende Webhooks pausiert, API, Worker und Outbox auf
null skaliert und ein geprüftes Datenbank-Backup erstellt. Erst danach folgt
`helm upgrade`; Traffic wird nach erfolgreichem Rollout und `/ready` wieder
freigegeben. Rein additive, ausdrücklich rückwärtskompatible Migrationen können
rollend ausgerollt werden.

Backups müssen PostgreSQL-Daten, Templateversionen und
`CREDENTIAL_ENCRYPTION_KEY` umfassen. Ohne diesen Schlüssel sind verschlüsselte
Paperless-API-Tokens und Webhook-Secrets nicht wiederherstellbar.
