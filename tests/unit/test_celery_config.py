from core.queue.celery_app import celery_app


def test_celery_configures_soft_and_independent_hard_time_limits() -> None:
    assert celery_app.conf.task_soft_time_limit == 360
    assert celery_app.conf.task_time_limit == 420
    assert celery_app.conf.result_expires == 3600
