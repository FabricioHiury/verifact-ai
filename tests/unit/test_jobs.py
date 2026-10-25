"""Job control tests with isolated database and mocked process execution."""

from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import sessionmaker
from verifact.models import Analysis, Status
from verifact_worker.jobs import process
from verifact_worker.media import PrerequisiteError
from verifact_worker.pipeline import Cancelled


class LockConnection:
    def scalar(self, *args, **kwargs):
        return True

    def execute(self, *args, **kwargs):
        return None

    def commit(self):
        pass


@contextmanager
def connection():
    yield LockConnection()


@pytest.mark.parametrize(
    "failure,expected",
    [
        (Cancelled(), Status.CANCELLED),
        (PrerequisiteError("missing token"), Status.PAUSED),
        (ValueError("bad model output"), Status.FAILED),
    ],
)
def test_job_failures_are_durable_without_fake_results(database, failure, expected):
    item = Analysis(title="Synthetic job", status=Status.QUEUED)
    database.add(item)
    database.commit()
    maker = sessionmaker(database.get_bind(), expire_on_commit=False)
    fake_engine = Mock()
    fake_engine.connect = connection
    pipeline = Mock()
    pipeline.kickoff.side_effect = failure
    with (
        patch("verifact_worker.jobs.factory", return_value=maker),
        patch("verifact_worker.jobs.engine", return_value=fake_engine),
        patch("verifact_worker.pipeline.Pipeline", return_value=pipeline),
    ):
        process.run(item.id)
    database.expire_all()
    assert database.get(Analysis, item.id).status == expected


def test_duplicate_completed_job_does_not_reexecute(database):
    item = Analysis(title="Synthetic completed job", status=Status.COMPLETED)
    database.add(item)
    database.commit()
    maker = sessionmaker(database.get_bind(), expire_on_commit=False)
    fake_engine = Mock()
    fake_engine.connect = connection
    with (
        patch("verifact_worker.jobs.factory", return_value=maker),
        patch("verifact_worker.jobs.engine", return_value=fake_engine),
        patch("verifact_worker.pipeline.Pipeline") as pipeline,
    ):
        process.run(item.id)
        pipeline.assert_not_called()


def test_periodic_recovery_reclaims_only_unowned_work(database):
    from verifact_worker.jobs import reconcile_stale_work

    running = Analysis(title="Synthetic orphan", status=Status.RUNNING)
    cancelled = Analysis(title="Synthetic cancellation", status=Status.CANCEL_REQUESTED)
    database.add_all([running, cancelled])
    database.commit()
    maker = sessionmaker(database.get_bind(), expire_on_commit=False)
    fake_engine = Mock()
    fake_engine.connect = connection
    with (
        patch("verifact_worker.jobs.factory", return_value=maker),
        patch("verifact_worker.jobs.engine", return_value=fake_engine),
    ):
        reconcile_stale_work()
    database.expire_all()
    assert database.get(Analysis, running.id).status == Status.QUEUED
    assert database.get(Analysis, cancelled.id).status == Status.CANCELLED


def test_recovery_waits_for_heavy_process_file_lock(database):
    import fcntl

    from verifact.config import settings
    from verifact_worker.jobs import reconcile_stale_work

    item = Analysis(title="Synthetic live child", status=Status.RUNNING)
    database.add(item)
    database.commit()
    maker = sessionmaker(database.get_bind(), expire_on_commit=False)
    fake_engine = Mock()
    fake_engine.connect = connection
    directory = settings().media_temp_dir
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "heavy.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with (
            patch("verifact_worker.jobs.factory", return_value=maker),
            patch("verifact_worker.jobs.engine", return_value=fake_engine),
        ):
            reconcile_stale_work()
    database.expire_all()
    assert database.get(Analysis, item.id).status == Status.RUNNING
