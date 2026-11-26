from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.database.base import Base

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            connect_args=settings.sqlite_connect_args(),
            future=True,
        )
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, class_=Session)
    return _SessionLocal


def SessionLocal():
    return get_session_factory()()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    settings = get_settings()
    Base.metadata.create_all(bind=get_engine())
    settings.resolved_upload_dir().mkdir(parents=True, exist_ok=True)
    settings.resolved_processed_dir().mkdir(parents=True, exist_ok=True)
    settings.resolved_analysis_dir().mkdir(parents=True, exist_ok=True)


def reset_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
