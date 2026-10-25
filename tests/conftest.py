import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from verifact.api import app
from verifact.db import session
from verifact.models import Base


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    from unittest.mock import Mock

    import httpx

    monkeypatch.setattr(
        "verifact_worker.pipeline.httpx.get",
        Mock(side_effect=httpx.ConnectError("No live metadata requests in synthetic tests")),
    )
    from verifact.config import settings

    config = settings()
    monkeypatch.setattr(config, "media_temp_dir", tmp_path / "tmp")
    monkeypatch.setattr(config, "local_storage_path", tmp_path / "storage")
    monkeypatch.setattr(config, "report_output_dir", tmp_path / "reports")
    monkeypatch.setattr(config, "storage_backend", "filesystem")
    monkeypatch.setattr(config, "min_free_disk_mb", 0)


@pytest.fixture
def database():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


@pytest.fixture
def client(database, monkeypatch):
    def override():
        yield database

    app.dependency_overrides[session] = override
    monkeypatch.setattr("verifact.api.enqueue", lambda identifier: None)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
