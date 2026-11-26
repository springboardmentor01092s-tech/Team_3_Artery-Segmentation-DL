from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select

from app.core.config import get_settings
from app.database.session import reset_engine
from app.models.user import User


def _alembic_config() -> Config:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    return config


def _run_upgrade(database_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()
    reset_engine()
    command.upgrade(_alembic_config(), "head")


def test_alembic_upgrade_creates_complete_schema_in_fresh_database(tmp_path, monkeypatch):
    database_path = tmp_path / "fresh.sqlite"
    _run_upgrade(database_path, monkeypatch)
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        tables = set(inspect(engine).get_table_names())
        assert {
            "users", "cases", "case_access", "uploaded_images", "preprocessing_runs",
            "audit_logs", "stenosis_analyses", "alembic_version",
        } <= tables
        with engine.connect() as connection:
            assert connection.execute(select(func.count()).select_from(User.__table__)).scalar_one() == 0
    finally:
        engine.dispose()
        reset_engine()
        get_settings.cache_clear()


def test_alembic_upgrade_preserves_existing_user_table_and_rows(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy.sqlite"
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        User.__table__.create(engine)
        with engine.begin() as connection:
            connection.execute(User.__table__.insert().values(
                id="preserved-user", full_name="Legacy User", email="legacy@example.invalid",
                password_hash="existing-hash", role="researcher", is_active=True,
            ))
    finally:
        engine.dispose()

    _run_upgrade(database_path, monkeypatch)
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.connect() as connection:
            row = connection.execute(
                select(User.id, User.email).where(User.id == "preserved-user")
            ).one()
            assert row.email == "legacy@example.invalid"
        assert "stenosis_analyses" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
        reset_engine()
        get_settings.cache_clear()
