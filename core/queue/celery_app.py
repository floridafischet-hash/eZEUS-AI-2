from celery import Celery

from core.config.settings import get_settings

settings = get_settings()
celery_app = Celery("ezeus", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    timezone="UTC",
    task_soft_time_limit=get_settings().ocr_timeout_seconds + 60,
)
celery_app.autodiscover_tasks(["apps.worker"])
