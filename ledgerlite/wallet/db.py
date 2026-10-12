from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ledgerlite.common.config import settings


@lru_cache
def engine():
    return create_engine(settings().database_url, pool_pre_ping=True, pool_size=10, max_overflow=10)


def session():
    with Session(engine()) as db:
        yield db
