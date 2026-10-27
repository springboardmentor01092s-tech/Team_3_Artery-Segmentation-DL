from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=create_engine(get_settings().sqlalchemy_url(), pool_pre_ping=False, connect_args={"connect_timeout": 5}), expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with get_session_factory()() as session:
        yield session
