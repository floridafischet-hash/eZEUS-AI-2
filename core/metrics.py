from prometheus_client import Counter, Gauge, Histogram, Info

app_info = Info("ezeus", "eZEUS-AI-2 application info")
app_info.info({"version": "0.2.0"})

JOBS_TOTAL = Counter(
    "ezeus_jobs_total",
    "Total jobs by terminal status and instance",
    ["status", "instance_slug"],
)

PHASE_DURATION_SECONDS = Histogram(
    "ezeus_phase_duration_seconds",
    "Phase execution duration in seconds",
    ["phase", "status"],
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
)

WEBHOOK_REQUESTS_TOTAL = Counter(
    "ezeus_webhook_requests_total",
    "Webhook requests by status code",
    ["status_code", "instance_slug"],
)

OUTBOX_EVENTS_TOTAL = Counter(
    "ezeus_outbox_events_total",
    "Outbox events by outcome",
    ["outcome"],
)

CELERY_QUEUE_DEPTH = Gauge(
    "ezeus_celery_queue_depth",
    "Number of tasks waiting in a Celery queue",
    ["queue"],
)
