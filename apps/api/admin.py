import hashlib
import hmac
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config.settings import get_settings
from core.db.session import get_db
from core.models.enums import JobStatus
from core.models.job import Job
from core.models.template import Template
from core.queue.adapter import QueueAdapter
from core.templates.schema import TemplateConfig

router = APIRouter(prefix="/api", tags=["administration"])


def require_admin_secret(x_ezeus_admin_secret: str | None = Header(default=None)) -> None:
    expected = get_settings().admin_api_secret
    if not expected or not x_ezeus_admin_secret:
        raise HTTPException(status_code=401, detail="Administrative authentication required")
    if not hmac.compare_digest(
        hashlib.sha256(x_ezeus_admin_secret.encode()).digest(),
        hashlib.sha256(expected.encode()).digest(),
    ):
        raise HTTPException(status_code=401, detail="Invalid administrative credentials")


class TemplateCreate(BaseModel):
    name: str
    document_type_external_id: str
    is_default: bool = True
    config: TemplateConfig


@router.post(
    "/templates",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_secret)],
)
def create_template(
    payload: TemplateCreate,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, object]:
    if payload.is_default:
        existing = db.scalar(
            select(Template).where(
                Template.document_type_external_id == payload.document_type_external_id,
                Template.is_default.is_(True),
                Template.enabled.is_(True),
            )
        )
        if existing:
            raise HTTPException(status_code=409, detail="An active default template already exists")
    latest = db.scalar(
        select(Template)
        .where(
            Template.document_type_external_id == payload.document_type_external_id,
            Template.name == payload.name,
        )
        .order_by(Template.version.desc())
    )
    template = Template(
        name=payload.name,
        document_type_external_id=payload.document_type_external_id,
        is_default=payload.is_default,
        version=(latest.version + 1) if latest else 1,
        config=payload.config.model_dump(),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return {"id": str(template.id), "version": template.version}


@router.post(
    "/jobs/{job_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin_secret)],
)
def retry_job(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in {JobStatus.FAILED, JobStatus.COMPLETED_WITH_WARNINGS}:
        raise HTTPException(status_code=409, detail="Job is not retryable in its current state")
    job.status = JobStatus.QUEUED
    job.error_type = None
    job.error_message = None
    job.finished_at = None
    db.commit()
    QueueAdapter().enqueue_document_job(job.id, job.priority)
    return {"job_id": str(job.id), "status": job.status.value}
