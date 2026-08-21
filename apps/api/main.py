import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from redis import Redis
from sqlalchemy import select, text

from apps.api.admin import router as admin_router
from apps.api.admin_users import router as admin_users_router
from apps.api.dashboard import router as dashboard_router
from apps.api.field_config import router as field_config_router
from apps.api.paperless_instances import router as paperless_instances_router
from connectors.base.errors import ConnectorError
from connectors.paperless.connector import PaperlessConnector
from core.config.settings import get_settings
from core.db.session import engine
from core.models.instance_field_config import InstanceFieldConfig
from core.security.outbound import OutboundRequestError, stream_capped, validate_outbound_url
from core.security.rate_limit import RateLimitMiddleware
from webhooks.paperless.router import router as paperless_webhook_router


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

READINESS_TIMEOUT_SECONDS = 5.0


def _database_readiness() -> tuple[bool, bool]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            ai_fields_enabled = bool(
                connection.scalar(
                    select(InstanceFieldConfig.id)
                    .where(
                        InstanceFieldConfig.enabled.is_(True),
                        InstanceFieldConfig.ai_enabled.is_(True),
                    )
                    .limit(1)
                )
            )
        return True, ai_fields_enabled
    except Exception:
        return False, False


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


async def _paperless_readiness() -> bool:
    try:
        return await PaperlessConnector().health_check()
    except ConnectorError:
        return False


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, object]:
    settings = get_settings()
    database_result, redis_ready, paperless_ready = await asyncio.gather(
        asyncio.to_thread(_database_readiness),
        asyncio.to_thread(_redis_readiness, settings.redis_url),
        _paperless_readiness(),
    )
    database_ready, ai_fields_enabled = database_result
    checks: dict[str, bool] = {
        "database": database_ready,
        "redis": redis_ready,
        "paperless": paperless_ready,
    }
    if settings.ollama_enabled or ai_fields_enabled:
        try:
            request_url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
            validate_outbound_url(request_url, settings=settings)
            async with httpx.AsyncClient(
                base_url=settings.ollama_base_url,
                timeout=min(settings.ollama_timeout_seconds, READINESS_TIMEOUT_SECONDS),
            ) as client:
                response, _ = await stream_capped(
                    client,
                    "GET",
                    request_url,
                    max_bytes=settings.ollama_max_response_bytes,
                )
                response.raise_for_status()
                models = response.json().get("models", [])
                checks["ollama"] = any(
                    item.get("name") == settings.ollama_model
                    or item.get("model") == settings.ollama_model
                    for item in models
                    if isinstance(item, dict)
                )
        except (httpx.HTTPError, OutboundRequestError, ValueError, TypeError):
            checks["ollama"] = False
    if not all(checks.values()):
        raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})
    return {"status": "ready", "checks": checks}
