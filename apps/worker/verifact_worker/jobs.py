import fcntl
import logging
from typing import Any

from celery.signals import worker_ready
from sqlalchemy import select, text
from verifact.config import settings
from verifact.db import engine, factory
from verifact.models import Analysis, AnalysisCancelled, Status

from verifact_worker.celery_app import app
from verifact_worker.media import PrerequisiteError

LOCK_ID = 734081921


@app.task(name="verifact.process", bind=True, max_retries=2)
def process(self: Any, analysis_id: str) -> None:
    from verifact_worker.pipeline import Pipeline

    cfg = settings()
    cfg.media_temp_dir.mkdir(parents=True, exist_ok=True)
    with engine().connect() as connection, (cfg.media_temp_dir / "heavy.lock").open("a") as lock:
        if not connection.scalar(text("SELECT pg_try_advisory_lock(:id)"), {"id": LOCK_ID}):
            raise self.retry(countdown=15, max_retries=cfg.max_retries)
        try:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise self.retry(countdown=15, max_retries=cfg.max_retries) from None
            with factory()() as db:
                item = db.get(Analysis, analysis_id)
                if not item or item.status not in (Status.QUEUED, Status.RUNNING):
                    return
                item.status = Status.RUNNING
                item.error = item.error_code = None
                db.commit()
            try:
                if cfg.social_download_enabled:
                    from verifact_worker.social import cleanup_orphans

                    cleanup_orphans()
                Pipeline(analysis_id, lock.fileno()).kickoff()
                state, error_code, message = Status.COMPLETED, None, None
            except AnalysisCancelled:
                state, error_code, message = Status.CANCELLED, None, None
            except PrerequisiteError as exc:
                state, error_code, message = Status.PAUSED, "PREREQUISITE", str(exc)
            except (ConnectionError, TimeoutError, OSError) as exc:
                with factory()() as db:
                    item = db.get(Analysis, analysis_id)
                    assert item
                    item.status = (
                        Status.QUEUED if self.request.retries < cfg.max_retries else Status.FAILED
                    )
                    item.error_code = "TRANSIENT_FAILURE"
                    item.error = "Falha transitória; confira serviços locais e retome se necessário"
                    db.commit()
                if self.request.retries < cfg.max_retries:
                    raise self.retry(
                        exc=RuntimeError(type(exc).__name__),
                        countdown=2 ** (self.request.retries + 1),
                        max_retries=cfg.max_retries,
                    ) from None
                return
            except Exception as exc:
                logging.getLogger("verifact").error(
                    "analysis_failed id=%s type=%s", analysis_id, type(exc).__name__
                )
                state, error_code, message = (
                    Status.FAILED,
                    "PIPELINE_ERROR",
                    "Falha de processamento ou validação. Confira pré-requisitos e retome; resultados não foram fabricados",
                )
            with factory()() as db:
                item = db.get(Analysis, analysis_id)
                assert item
                item.status = (
                    Status.PARTIALLY_COMPLETED
                    if state == Status.COMPLETED and item.limitations
                    else state
                )
                item.error_code, item.error = error_code, message
                db.commit()
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": LOCK_ID})
            connection.commit()


@app.task(name="verifact.dispatch")
def dispatch() -> int:
    reconcile_stale_work()
    with factory()() as db:
        ids = list(
            db.scalars(
                select(Analysis.id)
                .where(Analysis.status == Status.QUEUED)
                .order_by(Analysis.created_at)
                .limit(50)
            )
        )
    for identifier in ids:
        app.send_task("verifact.process", args=[identifier], retry=False)
    return len(ids)


def reconcile_stale_work() -> None:
    # Reclaim only with both locks: no replacement while a child still owns the file lock.
    cfg = settings()
    cfg.media_temp_dir.mkdir(parents=True, exist_ok=True)
    with engine().connect() as connection, (cfg.media_temp_dir / "heavy.lock").open("a") as lock:
        if not connection.scalar(text("SELECT pg_try_advisory_lock(:id)"), {"id": LOCK_ID}):
            return
        try:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            with factory()() as db:
                for item in db.scalars(
                    select(Analysis).where(
                        Analysis.status.in_([Status.RUNNING, Status.CANCEL_REQUESTED])
                    )
                ):
                    item.status = (
                        Status.QUEUED if item.status == Status.RUNNING else Status.CANCELLED
                    )
                db.commit()
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": LOCK_ID})
            connection.commit()


@worker_ready.connect
def recover(sender: Any = None, **kwargs: Any) -> None:
    reconcile_stale_work()
    dispatch.delay()


app.conf.beat_schedule = {
    "durable-dispatch": {"task": "verifact.dispatch", "schedule": 30.0, "options": {"expires": 25}}
}
