import os
from celery import Celery

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)

celery_app = Celery(
    "ai_stylist",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["app.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue="stylist_default",
    task_routes={
        "stylist.process_garment_reconstruction": {"queue": "garment_gpu"},
        "stylist.semantic_tag_garment_import": {"queue": "garment_gpu"},
        "stylist.handle_workflow_outbox_event": {"queue": "stylist_outbox"},
    },
    task_soft_time_limit=int(os.getenv("CELERY_SOFT_TIME_LIMIT", "3300")),
    task_time_limit=int(os.getenv("CELERY_TIME_LIMIT", "3600")),
    result_expires=int(os.getenv("CELERY_RESULT_EXPIRES", "3600")),
    timezone="UTC",
    enable_utc=True,
)
