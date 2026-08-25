import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from redis import Redis
from sqlalchemy import func, select, text

import core.metrics as _metrics  # noqa: F401 — registers Prometheus collectors
from apps.api.admin import router as admin_router
from apps.api.admin_users import router as admin_users_router
from apps.api.dashboard import router as dashboard_router
from apps.api.field_config import router as field_config_router
from apps.api.help import router as help_router
from apps.api.paperless_instances import router as paperless_instances_router
from apps.api.status import router as status_router
from core.config.settings import get_settings
from core.db.session import SessionLocal, engine
from core.logging import configure_logging
from core.models.enums import JobStatus
from core.models.job import Job
from core.models.queue_outbox import QueueOutbox
from core.queue.outbox import PENDING, PROCESSING
from core.security.rate_limit import RateLimitMiddleware
from webhooks.paperless.router import router as paperless_webhook_router

configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    engine.dispose()


app = FastAPI(title="eZEUS-AI-2", version="0.2.0", lifespan=lifespan)
app.add_middleware(RateLimitMiddleware, settings=get_settings())
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)
app.include_router(dashboard_router)
app.include_router(paperless_webhook_router)
app.include_router(admin_router)
app.include_router(admin_users_router)
app.include_router(paperless_instances_router)
app.include_router(field_config_router)
app.include_router(status_router)
app.include_router(help_router)

READINESS_TIMEOUT_SECONDS = 5.0


def _database_readiness() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _redis_readiness(redis_url: str) -> bool:
    client = Redis.from_url(
        redis_url,
        socket_connect_timeout=READINESS_TIMEOUT_SECONDS,
        socket_timeout=READINESS_TIMEOUT_SECONDS,
    )
    try:
        return bool(client.ping())
    except Exception:
        return False
    finally:
        client.close()


@app.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def metrics() -> PlainTextResponse:
    settings = get_settings()
    client = Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=READINESS_TIMEOUT_SECONDS,
        socket_timeout=READINESS_TIMEOUT_SECONDS,
    )
    try:
        client.ping()
        _metrics.BROKER_REACHABLE.set(1)
        for queue in ("high", "normal", "low"):
            depth = cast(int, client.llen(queue))
            _metrics.CELERY_QUEUE_DEPTH.labels(queue=queue).set(depth)
    except Exception:
        _metrics.BROKER_REACHABLE.set(0)
        for queue in ("high", "normal", "low"):
            _metrics.CELERY_QUEUE_DEPTH.labels(queue=queue).set(float("nan"))
    finally:
        client.close()
    try:
        with SessionLocal() as db:
            for status in (PENDING, PROCESSING):
                outbox_depth = db.scalar(
                    select(func.count(QueueOutbox.id)).where(QueueOutbox.status == status)
                )
                _metrics.OUTBOX_DEPTH.labels(status=status).set(int(outbox_depth or 0))
            stale_before = datetime.now(UTC) - timedelta(
                seconds=settings.sweeper_stale_threshold_seconds
            )
            for status in (
                JobStatus.RECEIVED,
                JobStatus.QUEUED,
                JobStatus.RUNNING,
                JobStatus.RETRY_WAITING,
            ):
                stalled = db.scalar(
                    select(func.count(Job.id)).where(
                        Job.status == status,
                        Job.updated_at <= stale_before,
                    )
                )
                _metrics.STALLED_JOBS.labels(status=status.value).set(int(stalled or 0))
    except Exception:
        for status in (PENDING, PROCESSING):
            _metrics.OUTBOX_DEPTH.labels(status=status).set(float("nan"))
        for status in (
            JobStatus.RECEIVED,
            JobStatus.QUEUED,
            JobStatus.RUNNING,
            JobStatus.RETRY_WAITING,
        ):
            _metrics.STALLED_JOBS.labels(status=status.value).set(float("nan"))
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, object]:
    settings = get_settings()
    try:
        database_ready, redis_ready = await asyncio.wait_for(
            asyncio.gather(
                asyncio.to_thread(_database_readiness),
                asyncio.to_thread(_redis_readiness, settings.redis_url),
            ),
            timeout=READINESS_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "checks": {"dependency_timeout": False}},
        ) from exc
    checks: dict[str, bool] = {
        "database": database_ready,
        "redis": redis_ready,
    }
    if not all(checks.values()):
        raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})
    return {"status": "ready", "checks": checks}
