import os

from celery import Celery
from verifact.config import settings

# Disable SDK telemetry before importing CrewAI, not just during a task.
os.environ["CREWAI_TELEMETRY_DISABLED"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
cfg = settings()
app = Celery(
    "verifact",
    broker=cfg.celery_broker_url.get_secret_value(),
    backend=cfg.celery_result_backend.get_secret_value(),
    include=["verifact_worker.jobs"],
)
app.conf.update(
    worker_pool="solo",
    worker_concurrency=cfg.celery_worker_concurrency,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    broker_transport_options={"visibility_timeout": 86400},
    result_expires=3600,
)
