from uuid import UUID

from core.models.enums import JobPriority
from core.queue.celery_app import celery_app

QUEUE_BY_PRIORITY = {
    JobPriority.HIGH: "high",
    JobPriority.NORMAL: "normal",
    JobPriority.LOW: "low",
}


class QueueAdapter:
    def enqueue_document_job(self, job_id: UUID, priority: JobPriority) -> None:
        celery_app.send_task(
            "ezeus.process_document_job",
            args=[str(job_id)],
            queue=QUEUE_BY_PRIORITY[priority],
        )
