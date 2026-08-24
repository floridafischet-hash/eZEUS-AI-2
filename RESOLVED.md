# Resolution report

This report answers the findings in `DEFECTS.md` against the implementation in
commit `c7db1b5` and the earlier commits referenced per finding.

## K8S-1 — Resolved

**Decision:** Resolved  
**Commit:** `c7db1b5`  
**Changed:** `apps/api/main.py`, `apps/api/status.py`, `tests/test_health.py`,
`tests/test_status.py`

**What I did:** `/ready` now checks only PostgreSQL and Redis. Paperless instances
and Ollama moved to the authenticated, informational `/status/dependencies`
endpoint. External customer or inference outages can no longer remove API pods
from the Kubernetes Service.

**Why this and not something else:** Readiness is a traffic-admission signal and
must cover only dependencies required to serve requests. External tenant systems
remain visible to operators without becoming load-bearing for pod readiness.

**Verification:**

```text
$ DATABASE_URL=postgresql+psycopg://... REDIS_URL=redis://127.0.0.1:56380/0 \
  OLLAMA_ENABLED=false PAPERLESS_BASE_URL=http://127.0.0.1:1 \
  curl http://127.0.0.1:18084/ready
{"status":"ready","checks":{"database":true,"redis":true}}
HTTP 200

$ python -m pytest tests/test_health.py tests/test_status.py -q
......                                                                   [100%]
```

**Residual risk:** The informational endpoint reports reachability on demand;
operators still need Prometheus or another monitor to poll and alert on it.

## UI-1 — Resolved

**Decision:** Resolved  
**Commit:** `62196b8`  
**Changed:** `apps/api/ui.py`

**What I did:** Removed the complete joke span and its separator from the
breadcrumb bar.

**Why this and not something else:** The text had no product function, so removal
is safer than replacing it with another hard-coded label.

**Verification:**

```text
$ grep -rn 'Peiffen' --include='*.py' .
(no output)
```

**Residual risk:** None identified.

## SEC-1 — Resolved

**Decision:** Resolved  
**Commit:** `62196b8`  
**Changed:** `core/security/admin_auth.py`,
`deploy/helm/ezeus-ai-2/templates/ingress.yaml`,
`deploy/helm/ezeus-ai-2/templates/networkpolicy.yaml`

**What I did:** Removed the `X-EZEUS-Proxy-User` and shared proxy-secret
authentication path. The Ingress clears inbound `X-EZEUS-Proxy-*` headers and
the NetworkPolicy restricts API ingress to the expected proxy/controller pods.

**Why this and not something else:** A reusable shared header secret cannot prove
request origin. Deleting that identity path closes impersonation instead of
adding another assumption around it.

**Verification:**

```text
$ python -m pytest tests/test_field_configuration.py::test_proxy_headers_are_ignored -q
.                                                                        [100%]
```

**Residual risk:** Administrative authentication currently remains application
Basic/header credential based. OIDC group-to-role mapping is not implemented in
the application.

## STA-1 — Resolved

**Decision:** Resolved  
**Commit:** `62196b8`, `b210106`  
**Changed:** `core/queue/sweeper.py`, `apps/api/admin.py`, Helm sweeper manifests

**What I did:** Added a periodic sweeper for stale active jobs. It requeues jobs
transactionally through the outbox while retries remain and fails exhausted jobs.
The manual retry endpoint accepts stuck active states.

**Why this and not something else:** Reusing the transactional outbox preserves
the existing delivery guarantees and releases the partial unique constraint
without direct production SQL.

**Verification:**

```text
$ python -m pytest tests/unit/test_sweeper.py -q
.....                                                                    [100%]
```

**Residual risk:** `updated_at` is the heartbeat proxy. A single phase that
legitimately runs longer than the threshold must be covered by an appropriately
sized `SWEEPER_STALE_THRESHOLD_SECONDS` value.

## DAT-1 — Resolved

**Decision:** Resolved  
**Commit:** `62196b8`, `b210106`  
**Changed:** `connectors/paperless/connector.py`,
`core/models/paperless_instance.py`, migration `0010`

**What I did:** Titles are written only when empty or still equal to the original
filename. Per-instance overwrite is available as an explicit opt-in and defaults
to false.

**Why this and not something else:** This matches the connector's other
fill-only write paths while retaining an intentional escape hatch.

**Verification:**

```text
$ python -m pytest tests/unit/test_write_title.py -q
........                                                                 [100%]
```

**Residual risk:** An operator enabling `allow_title_overwrite` explicitly
accepts replacement of human-curated titles.

## SEC-5 — Resolved

**Decision:** Resolved  
**Commit:** `799f231`, `8a4e937`  
**Changed:** `core/paperless/service.py`, `tests/unit/test_paperless_service.py`

**What I did:** Candidate credentials are decrypted inside a per-instance
try/except. Unreadable credentials are skipped with a structured warning, so a
healthy matching tenant remains resolvable.

**Why this and not something else:** Failing the whole unscoped route reproduces
the cross-tenant outage. Skipping only the corrupt candidate isolates the fault.

**Verification:**

```text
$ python -m pytest tests/unit/test_paperless_service.py -q
...                                                                      [100%]
```

**Residual risk:** The affected tenant remains unavailable until its credential
is repaired; the warning and dependency status must be monitored.

## SEC-6 — Resolved

**Decision:** Resolved  
**Commit:** `3c73f7d`  
**Changed:** `core/security/credentials.py`, `scripts/rotate_credentials.py`,
Helm documentation

**What I did:** Credential operations use an ordered `MultiFernet` keyring. The
first key encrypts and all configured keys decrypt. The legacy single-key setting
remains supported, and the rotation command rewrites stored credentials.

**Why this and not something else:** This is Fernet's standard online rotation
model and permits a staged rotation without an all-at-once outage.

**Verification:**

```text
$ python -m pytest tests/unit/test_credentials.py -q
...                                                                      [100%]
```

**Residual risk:** Losing every key in the keyring remains unrecoverable. A
verified key backup is operationally mandatory.

## OBS-1 — Resolved

**Decision:** Resolved  
**Commit:** `62196b8`, `c7db1b5`  
**Changed:** `core/logging.py`, orchestrator, worker, connector and webhook paths,
`tests/unit/test_logging.py`

**What I did:** Added JSON logging to stdout with job, instance, phase, worker and
document context. Phase transitions, worker lifecycle, connector failures and
webhook rejection paths now log structured events.

**Why this and not something else:** Standard-library logging keeps integration
small while producing collector-friendly one-line JSON.

**Verification:**

```text
$ python -m pytest tests/unit/test_logging.py -q
.                                                                        [100%]
```

**Residual risk:** Distributed tracing and correlation across third-party
Paperless requests are not implemented.

## OBS-2 — Resolved

**Decision:** Resolved  
**Commit:** `62196b8`, `c7db1b5`  
**Changed:** `core/metrics.py`, `apps/api/main.py`, ServiceMonitor and
PrometheusRule Helm templates

**What I did:** `/metrics` exposes job counters by status and instance, phase
duration histograms, webhook/outbox counters, Celery queue depth, current outbox
depth, broker reachability and stale active jobs. Optional Prometheus rules cover
broker loss, stuck jobs, outbox backlog and sustained failure rate.

**Why this and not something else:** These are the direct service-level signals
needed for alerting and queue-oriented capacity decisions without introducing a
second telemetry stack.

**Verification:**

```text
$ python -m pytest tests/test_health.py::test_metrics_exposes_queue_outbox_and_stalled_job_series -q
.                                                                        [100%]

$ make helm-check
Summary: 54 resources found in 2 files - Valid: 54, Invalid: 0, Errors: 0, Skipped: 0
```

**Residual risk:** PrometheusRule and ServiceMonitor are disabled by default
because their CRDs are optional. Operators must enable them when the Prometheus
Operator is installed.

## DAT-2 — Resolved

**Decision:** Resolved  
**Commit:** `c7db1b5`  
**Changed:** `core/models/paperless_instance.py`,
`apps/api/paperless_instances.py`, migration `0013`

**What I did:** Instance deletion is now a soft delete. The disabled instance row
and unique slug remain as a tombstone, deleted instances are excluded from API,
webhook, dashboard and field-configuration lookup, and audit foreign keys remain
intact.

**Why this and not something else:** Refusing all deletion would leave operators
without the requested lifecycle operation. A separate retired-slug table would
prevent reuse but preserve less tenant context. Soft delete solves both problems
with one durable identity.

**Verification:**

```text
$ python -m pytest tests/test_paperless_instances.py -q
.........                                                                [100%]
```

**Residual risk:** Tombstones retain encrypted credentials. They remain protected
by the credential keyring but require a future retention policy if cryptographic
erasure is required.

## SEC-2 — Resolved

**Decision:** Resolved  
**Commit:** `62196b8`, `b210106`  
**Changed:** `apps/api/dashboard.py`, `tests/test_dashboard.py`

**What I did:** `/api/logs` requires in-application admin authentication. Limits
were reduced, sensitive errors and phase metadata strings are redacted, and the
result is paginated.

**Why this and not something else:** In-app authorization keeps a Service or
Ingress routing mistake from becoming a data disclosure.

**Verification:**

```text
$ python -m pytest tests/test_dashboard.py::test_processing_logs_require_authentication -q
.                                                                        [100%]
```

**Residual risk:** The public UI shell and OpenAPI pages remain reachable when
exposed outside the authenticated Ingress, but the operational data endpoint
itself rejects unauthenticated access.

## STA-3 — Resolved

**Decision:** Resolved  
**Commit:** `e0ff751`, `b210106`  
**Changed:** `core/config/settings.py`, `core/queue/celery_app.py`

**What I did:** Added an independent configurable Celery hard task limit and
validated that it exceeds the soft inference-related bound.

**Why this and not something else:** A hard Celery limit can terminate a wedged
child process when Python-level cancellation cannot.

**Verification:**

```text
$ python -m pytest tests/unit/test_celery_config.py tests/unit/test_settings.py -q
...........                                                              [100%]
```

**Residual risk:** Hard termination can interrupt a foreign call between request
completion and local state persistence; idempotent writes and late acknowledgments
remain necessary.

## STA-4 — Resolved

**Decision:** Resolved  
**Commit:** `49508e4`  
**Changed:** `core/orchestration/exceptions.py`, orchestrator and worker task

**What I did:** Empty Paperless text raises `RetryableEmptyTextError`; the worker
uses the existing retry contract and backoff rather than completing an empty job.

**Why this and not something else:** Empty content immediately after a webhook is
usually an upstream OCR race, not a successful extraction result.

**Verification:**

```text
$ python -m pytest tests/unit/test_orchestrator_empty_text.py -q
..                                                                       [100%]
```

**Residual risk:** Permanently textless documents consume retries and eventually
fail, as intended, rather than being silently accepted.

## OBS-3 — Resolved

**Decision:** Resolved  
**Commit:** `62196b8`, `b210106`  
**Changed:** `apps/api/dashboard.py`, migration `0011`

**What I did:** Added stable `(created_at, id)` cursor pagination, a default page
size of 50, a matching composite index and an explicit “Mehr laden” UI flow.

**Why this and not something else:** A keyset cursor remains stable when several
jobs share a timestamp and avoids increasingly expensive offsets.

**Verification:**

```text
$ python -m pytest tests/test_dashboard.py -q
........                                                                 [100%]
```

**Residual risk:** Each page still includes phase details for its jobs; unusually
large phase histories can make an individual page heavy.

## SCA-1 — Resolved

**Decision:** Resolved  
**Commit:** `5a3ed17`  
**Changed:** `connectors/paperless/connector.py`, orchestrator lifecycle

**What I did:** PaperlessConnector lazily owns one `httpx.AsyncClient` for the job
lifetime and explicitly closes it through `close`/async context management.

**Why this and not something else:** Per-job reuse provides connection pooling
without creating a process-global client with unclear tenant credentials.

**Verification:**

```text
$ python -m pytest tests/unit/test_paperless_client_lifecycle.py -q
.                                                                        [100%]
```

**Residual risk:** Connections are not shared across jobs, intentionally keeping
tenant and lifecycle boundaries simple.

## SCA-2 — Resolved

**Decision:** Resolved  
**Commit:** `561940e`  
**Changed:** connector write helpers and orchestrator `RELOAD_METADATA`

**What I did:** The single reloaded document snapshot is passed into title,
custom-field and correspondent write helpers instead of fetching the document
again in each helper.

**Why this and not something else:** The explicit reload remains the write-time
consistency boundary while redundant network calls disappear.

**Verification:**

```text
$ python -m pytest tests/unit/test_write_title.py -q
........                                                                 [100%]
```

**Residual risk:** Concurrent Paperless edits after the reload and before PATCH
remain a normal optimistic-concurrency window.

## SCA-3 — Resolved

**Decision:** Resolved  
**Commit:** `d752457`  
**Changed:** `core/config/settings.py`, `core/db/session.py`, Helm documentation

**What I did:** Pool size, overflow and timeout are independently configurable
and passed to SQLAlchemy. Documentation relates total connections to replica and
process counts and reserves PostgreSQL capacity for administration.

**Why this and not something else:** Operators need to size the aggregate across
replicas; increasing a hard-coded default would only move the bottleneck.

**Verification:**

```text
$ python -m pytest tests/unit/test_settings.py -q
..........                                                               [100%]
```

**Residual risk:** Incorrect operator sizing can still exhaust an external
PostgreSQL service; the documented formula must be applied per deployment.

## CFG-1 — Resolved

**Decision:** Resolved  
**Commit:** `62196b8`  
**Changed:** `core/field_config/service.py`

**What I did:** The Ollama provider is added only when both the field and global
Ollama switch are enabled. Disabled inference cleanly leaves regex providers.

**Why this and not something else:** Excluding the provider before invocation
prevents network exceptions and makes the global switch a real kill switch.

**Verification:**

```text
$ python -m pytest tests/test_field_configuration.py::test_ollama_disabled_degrades_to_regex_only -q
.                                                                        [100%]
```

**Residual risk:** Enabling Ollama with an unreachable configured endpoint still
causes the normal provider failure and retry behavior.

## MIG-1 — Resolved

**Decision:** Resolved for future upgrades; historical loss explicitly documented  
**Commit:** `c7db1b5`  
**Changed:** migrations `0007` and `0008`, Helm schema-upgrade documentation

**What I did:** Migration 0007 no longer deletes `RUN_OCR` and `WRITE_OCR` rows.
It maps them to `READ_DOCUMENT_TEXT`, retains timestamps, errors and metadata,
and stores the original name in `metadata.legacy_phase`. Downgrade restores the
exact original phase and removes the marker. Backup requirements and the
irrecoverability of rows deleted by an already-run older migration are explicit.

**Why this and not something else:** Keeping obsolete enum labels forever would
block enum cleanup. Preserving the rows plus their original semantic label keeps
history without retaining retired runtime values.

**Verification:**

```text
$ MIGRATION_TEST_DATABASE_URL=postgresql+psycopg://... \
  python -m pytest tests/integration/test_migration_roundtrip.py -q
.                                                                        [100%]
```

The seeded PostgreSQL check also reported two rows before upgrade, two retained
rows after upgrade, and restored phases `RUN_OCR` and `WRITE_OCR` after downgrade.

**Residual risk:** Rows already deleted by an older execution of migration 0007
cannot be reconstructed. Those installations must restore from a pre-upgrade
backup if the history is required.

## SCA-4 — Resolved

**Decision:** Resolved  
**Commit:** `8a4e937`  
**Changed:** indexed `webhook_secret_hmac`, lookup service and migration `0012`

**What I did:** The unscoped webhook computes a keyed HMAC and performs an indexed
candidate lookup before decrypting. Plaintext comparison remains constant-time.

**Why this and not something else:** This retains backward compatibility for the
unscoped endpoint while removing the linear decrypt-all-tenants path.

**Verification:**

```text
$ python -m pytest tests/unit/test_paperless_service.py -q
...                                                                      [100%]
```

**Residual risk:** The unscoped endpoint remains a supported compatibility path;
operators can disable it at the Ingress after migrating to per-instance URLs.

## SCA-5 — Mitigated

**Decision:** Mitigated  
**Commit:** `ba4322c`  
**Changed:** `core/queue/outbox.py`, queue settings and tests

**What I did:** Jobs for an instance at its configurable in-flight limit are
routed to the low-priority queue. Jobs from another instance below its limit stay
normal priority and can be published immediately.

**Why this and not something else:** This is a bounded change compatible with the
existing three queues. Per-tenant queues would add unbounded dynamic routing and
worker subscription management.

**Verification:**

```text
$ python -m pytest tests/unit/test_queue_outbox.py::test_busy_instance_is_downgraded_without_delaying_other_instance -q
.                                                                        [100%]
```

**Residual risk:** This is priority isolation, not strict round-robin fairness.
If low-priority work is starved indefinitely or worker queue ordering is changed,
a dedicated fair scheduler would still be required.

## MIG-2 — Resolved

**Decision:** Resolved  
**Commit:** `c7db1b5`  
**Changed:** migrations `0007` and `0008`, PostgreSQL CI migration test

**What I did:** The 0008 downgrade now recreates a transition enum containing
`READ_DOCUMENT_TEXT`; migration 0007 then owns the rename back to
`DOWNLOAD_DOCUMENT`. CI performs upgrade, downgrade and upgrade against
PostgreSQL 16 with seeded legacy phase history.

**Why this and not something else:** Keeping the rename in its owning migration
avoids double-renaming and makes each revision boundary valid and atomic.

**Verification:**

```text
$ MIGRATION_TEST_DATABASE_URL=postgresql+psycopg://... \
  python -m pytest tests/integration/test_migration_roundtrip.py -q
.                                                                        [100%]
```

**Residual risk:** Downgrade is tested to revision 0006, not as a supported
application rollback guarantee across arbitrary future revisions.

## Full regression result

```text
$ python -m pytest -ra
168 passed, 1 skipped in 5.28s
```

The one skipped test is the destructive migration round-trip unless
`MIGRATION_TEST_DATABASE_URL` explicitly points to a disposable PostgreSQL
database. It was run separately against PostgreSQL 16 and passed.

```text
$ make lint && make format-check && make typecheck && make security
All checks passed!
154 files already formatted
Success: no issues found in 89 source files
No known vulnerabilities found

$ make container-smoke
Administrator 'smoke-admin' created.
Container smoke test passed for job 04c5003e-b08d-490d-87e9-351d5ad292f7
```
