"""Configurable, bounded local file logging for the application namespace."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


_HANDLER_MARKER = "_artery_preprocessing_handler"


def configure_logging(settings) -> Path:
    """Configure rotating app logs and return the resolved log path.

    Only loggers under ``app`` receive this handler. Repeated startup/config
    calls replace the prior app-owned handler rather than duplicating output.
    """
    path = settings.resolved_log_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    level = getattr(logging, settings.log_level, None)
    if not isinstance(level, int):
        raise ValueError("LOG_LEVEL must be a supported Python logging level.")

    app_logger = logging.getLogger("app")
    for existing in list(app_logger.handlers):
        if getattr(existing, _HANDLER_MARKER, False):
            app_logger.removeHandler(existing)
            existing.close()

    handler = RotatingFileHandler(
        path,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    ))
    setattr(handler, _HANDLER_MARKER, True)
    app_logger.addHandler(handler)
    app_logger.setLevel(level)
    app_logger.propagate = False
    return path
