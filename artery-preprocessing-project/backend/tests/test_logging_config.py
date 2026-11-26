import logging

from app import main
from app.core.config import Settings
from app.core.logging_config import configure_logging


def _remove_app_file_handlers():
    app_logger = logging.getLogger("app")
    for handler in list(app_logger.handlers):
        if getattr(handler, "_artery_preprocessing_handler", False):
            app_logger.removeHandler(handler)
            handler.close()
    app_logger.setLevel(logging.NOTSET)
    app_logger.propagate = True


def test_configured_logging_writes_and_rotates_with_bounded_backups(tmp_path):
    log_path = tmp_path / "logs" / "application.log"
    settings = Settings(
        _env_file=None,
        log_file=str(log_path),
        log_level="debug",
        log_max_bytes=1024,
        log_backup_count=2,
    )
    try:
        assert configure_logging(settings) == log_path
        logger = logging.getLogger("app.tests.logging")
        for index in range(100):
            logger.info("safe test event %03d %s", index, "x" * 80)
        for handler in logging.getLogger("app").handlers:
            if getattr(handler, "_artery_preprocessing_handler", False):
                handler.flush()
        assert log_path.is_file()
        assert "safe test event" in log_path.read_text(encoding="utf-8")
        rotations = list(log_path.parent.glob("application.log.*"))
        assert 1 <= len(rotations) <= 2
        assert settings.resolved_log_file() == log_path
    finally:
        _remove_app_file_handlers()


def test_reconfiguring_logging_replaces_handler_without_duplicates(tmp_path):
    first = Settings(_env_file=None, log_file=str(tmp_path / "first.log"))
    second = Settings(_env_file=None, log_file=str(tmp_path / "second.log"))
    try:
        configure_logging(first)
        configure_logging(second)
        owned = [h for h in logging.getLogger("app").handlers if getattr(h, "_artery_preprocessing_handler", False)]
        assert len(owned) == 1
        logging.getLogger("app.tests.logging").warning("second destination event")
        owned[0].flush()
        assert (tmp_path / "second.log").is_file()
        assert "second destination event" in (tmp_path / "second.log").read_text(encoding="utf-8")
        if (tmp_path / "first.log").exists():
            assert (tmp_path / "first.log").read_text(encoding="utf-8") == ""
    finally:
        _remove_app_file_handlers()


def test_application_startup_configures_logging_before_database(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "configure_logging", lambda _settings: calls.append("logging"))
    monkeypatch.setattr(main, "init_db", lambda: calls.append("database"))
    main.on_startup()
    assert calls == ["logging", "database"]
