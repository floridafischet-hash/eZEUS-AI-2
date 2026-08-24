import asyncio
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from connectors.base.errors import ConnectorError
from core.config.settings import get_settings
from core.db.session import get_db
from core.models.paperless_instance import PaperlessInstance
from core.paperless.service import connector_for_instance
from core.security.admin_auth import require_admin_user
from core.security.credentials import CredentialEncryptionError
from core.security.outbound import OutboundRequestError, stream_capped, validate_outbound_url

router = APIRouter()


async def _paperless_status(instance: PaperlessInstance) -> dict[str, object]:
    try:
        async with connector_for_instance(instance) as connector:
            reachable = await connector.health_check()
        return {"slug": instance.slug, "reachable": reachable}
    except (ConnectorError, CredentialEncryptionError):
        return {"slug": instance.slug, "reachable": False}


async def _ollama_status() -> dict[str, object]:
    settings = get_settings()
    if not settings.ollama_enabled:
        return {"enabled": False, "reachable": None, "model_available": None}
    try:
        request_url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
        validate_outbound_url(request_url, settings=settings)
        async with httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=min(settings.ollama_timeout_seconds, 5.0),
        ) as client:
            response, _ = await stream_capped(
                client,
                "GET",
                request_url,
                max_bytes=settings.ollama_max_response_bytes,
            )
            response.raise_for_status()
            models = response.json().get("models", [])
        available = any(
            item.get("name") == settings.ollama_model or item.get("model") == settings.ollama_model
            for item in models
            if isinstance(item, dict)
        )
        return {"enabled": True, "reachable": True, "model_available": available}
    except (httpx.HTTPError, OutboundRequestError, ValueError, TypeError):
        return {"enabled": True, "reachable": False, "model_available": False}


@router.get("/status/dependencies", dependencies=[Depends(require_admin_user)])
async def dependency_status(db: Annotated[Session, Depends(get_db)]) -> dict[str, object]:
    instances = db.scalars(
        select(PaperlessInstance)
        .where(
            PaperlessInstance.enabled.is_(True),
            PaperlessInstance.deleted_at.is_(None),
        )
        .order_by(PaperlessInstance.slug)
    ).all()
    paperless = await asyncio.gather(*(_paperless_status(instance) for instance in instances))
    return {
        "informational": True,
        "paperless": list(paperless),
        "ollama": await _ollama_status(),
    }
