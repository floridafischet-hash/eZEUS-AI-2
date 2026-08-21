# eZEUS-AI-2 Helm Chart

Deploys the FastAPI API, Celery worker, transactional outbox dispatcher,
PostgreSQL, Redis and optional Ollama.

## Validate locally

```bash
make helm-check
```

This runs Helm lint, renders default and production-example values, and checks
all generated resources with kubeconform in strict mode. `values.schema.json`
also rejects invalid value types during Helm operations.

## Install

1. Build the exact application revision and publish its immutable version tag
   to the registry used by the cluster:

```bash
docker build --tag registry.example/ezeus-ai-2:0.2.0 .
docker push registry.example/ezeus-ai-2:0.2.0
```

   Set `image.repository`, `image.tag` and, for a private registry,
   `imagePullSecrets` to match. The chart never builds or silently substitutes
   an image.
2. Copy `values-production.example.yaml` outside the chart and replace every
   example domain/CIDR.
3. Provision the Secret named by `existingSecret` through Sealed Secrets,
   External Secrets or the platform secret manager. It must contain
   `DATABASE_URL` (for an external DB), `PAPERLESS_API_TOKEN`,
   `PAPERLESS_WEBHOOK_SECRET`, `CREDENTIAL_ENCRYPTION_KEY`, and, when OIDC is
   enabled, `OAUTH2_PROXY_CLIENT_SECRET` and `OAUTH2_PROXY_COOKIE_SECRET`.
4. Install the release:

```bash
helm upgrade --install ezeus deploy/helm/ezeus-ai-2 \
  --namespace ezeus --create-namespace \
  --values values-production.yaml \
  --wait --timeout 10m
```

Do not pass secrets with `--set`; command lines are commonly retained in shell
history and process metadata.

## Production checklist

- `image.tag` pinned to a specific version, not `latest`.
- `existingSecret` points to a Sealed/External Secret; leave `secrets` empty.
- `ingress.enabled=true` with `tls` and `cert-manager.io/cluster-issuer` annotation set.
- `oauth2Proxy.enabled=true` for browser traffic; only `/oauth2`, webhook paths
  and `/health` bypass the main auth request. `/ready`, dashboard, logs and
  OpenAPI remain protected externally.
- `networkPolicy.enabled=true` and `allowedIngressNamespaces` scoped to your ingress-nginx namespace.
- `networkPolicy.egressCidrs` contains the exact Paperless, database, Redis,
  Ollama and OIDC ranges required by this installation. The TEST-NET range in
  the example is intentionally non-functional. Unrestricted `0.0.0.0/0` and
  `::/0` ranges are rejected by the values schema.
- HPA + PDB enabled for `api` and `worker`.
- For managed databases: `postgres.enabled=false` and `DATABASE_URL` stored in
  `existingSecret` (or a credential-free URL in `external.databaseUrl`).
- The bundled PostgreSQL, Redis and Ollama StatefulSets are single-instance
  building blocks, not HA clusters. Use managed/external services and tested
  backups when the installation requires high availability.
- Keep `migrations.helmHookEnabled=false` with internal PostgreSQL. For an
  already reachable external database it may be enabled as in the production
  example.

See `values-production.example.yaml` for a full example.

## Schema upgrades

The PostgreSQL advisory lock serializes Alembic processes; it does not make an
old application version compatible with every future destructive migration.
For releases that remove or rewrite schema, pause inbound webhooks, scale the
API, worker and outbox Deployments to zero, take and verify a database backup,
then run `helm upgrade`. Resume traffic only after migrations, rollout and
`/ready` have succeeded. Additive, explicitly backward-compatible migrations
may use the normal rolling path.

## Included manifests

- `api-deployment.yaml`, `api-service.yaml`, `api-hpa.yaml`, `api-pdb.yaml`
- `worker-deployment.yaml`, `worker-hpa.yaml`, `worker-pdb.yaml`
- `outbox-deployment.yaml`
- `postgres-statefulset.yaml`, `postgres-service.yaml`
- `redis-statefulset.yaml`, `redis-service.yaml`
- `ollama-statefulset.yaml`, `ollama-service.yaml`
- migration init containers with a PostgreSQL advisory lock; optional
  `migrations-job.yaml` hook for external databases
- `ingress.yaml` (main + optional public-webhook bypass ingress)
- `oauth2-proxy.yaml` (optional OIDC authentication)
- `networkpolicy.yaml` (workload-specific ingress/egress allow rules)
- `configmap.yaml`, `secret.yaml`, `serviceaccount.yaml`, `NOTES.txt`

## Non-root containers

Every application pod runs as UID 10001 with `readOnlyRootFilesystem: true`,
seccomp `RuntimeDefault`, dropped capabilities and
`allowPrivilegeEscalation: false`. Writable temporary paths use size-limited
`emptyDir` volumes. No application process needs a root start.
