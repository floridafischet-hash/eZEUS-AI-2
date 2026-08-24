from celery import Celery

from core.config.settings import get_settings
from core.logging import configure_logging

configure_logging()

settings = get_settings()
celery_app = Celery("ezeus", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    worker_hijack_root_logger=False,
    timezone="UTC",
    task_soft_time_limit=settings.ollama_timeout_seconds + 60,
    task_time_limit=settings.celery_task_time_limit_seconds,
    result_expires=settings.celery_result_expires_seconds,
)
celery_app.autodiscover_tasks(["apps.worker"])
