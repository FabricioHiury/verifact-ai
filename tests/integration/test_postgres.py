"""Opt-in real PostgreSQL checks; isolated schema, never touches application tables."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from verifact.config import settings
from verifact.models import Analysis, Base, Speaker


@pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_TESTS") != "1",
    reason="Set RUN_POSTGRES_TESTS=1 for real PostgreSQL",
)
def test_postgres_relations_and_rollback():
    database = create_engine(settings().database_url.get_secret_value())
    schema = "test_" + uuid4().hex
    with database.connect() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET search_path TO "{schema}"'))
        connection.commit()
        try:
            Base.metadata.create_all(connection)
            connection.commit()
            with Session(bind=connection) as db:
                analysis = Analysis(title="Isolated PostgreSQL fixture")
                db.add(analysis)
                db.flush()
                db.add(Speaker(analysis_id=analysis.id, cluster="UNKNOWN"))
                db.commit()
                assert db.get(Analysis, analysis.id).title == "Isolated PostgreSQL fixture"
                analysis.title = "rolled back"
                db.rollback()
                assert db.get(Analysis, analysis.id).title == "Isolated PostgreSQL fixture"
        finally:
            connection.rollback()
            connection.execute(text("SET search_path TO public"))
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            connection.commit()
    database.dispose()
