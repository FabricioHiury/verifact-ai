from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from verifact.config import settings


@lru_cache
def engine() -> Engine:
    return create_engine(settings().database_url.get_secret_value(), pool_pre_ping=True)


def session() -> Iterator[Session]:
    with Session(engine()) as db:
        yield db


def factory() -> sessionmaker[Session]:
    return sessionmaker(engine(), expire_on_commit=False)
