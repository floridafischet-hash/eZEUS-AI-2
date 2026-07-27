from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from redis import Redis
from sqlalchemy import text

from apps.api.admin import router as admin_router
from connectors.base.errors import ConnectorError
from connectors.paperless.connector import PaperlessConnector
from core.config.settings import get_settings
from core.db.session import engine
from plugins.ocr.factory import create_ocr_adapter
from webhooks.paperless.router import router as paperless_webhook_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    engine.dispose()


app = FastAPI(title="eZEUS-AI-2", version="0.2.0", lifespan=lifespan)
app.include_router(paperless_webhook_router)
app.include_router(admin_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, object]:
    settings = get_settings()
    checks: dict[str, bool] = {}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False
    try:
        checks["redis"] = bool(Redis.from_url(settings.redis_url).ping())
    except Exception:
        checks["redis"] = False
    try:
        checks["paperless"] = await PaperlessConnector().health_check()
    except ConnectorError:
        checks["paperless"] = False
    try:
        create_ocr_adapter()
        checks["ocr"] = True
    except (RuntimeError, ValueError):
        checks["ocr"] = False
    if settings.ollama_enabled:
        try:
            async with httpx.AsyncClient(
                base_url=settings.ollama_base_url,
                timeout=min(settings.ollama_timeout_seconds, 15),
            ) as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                models = response.json().get("models", [])
                checks["ollama"] = any(
                    item.get("name") == settings.ollama_model
                    or item.get("model") == settings.ollama_model
                    for item in models
                    if isinstance(item, dict)
                )
        except (httpx.HTTPError, ValueError, TypeError):
            checks["ollama"] = False
    if not all(checks.values()):
        raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})
    return {"status": "ready", "checks": checks}
