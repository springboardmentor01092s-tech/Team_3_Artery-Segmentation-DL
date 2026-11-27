from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import math

from sqlalchemy import case, delete
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.security_state import LoginRateLimitBucket


def _bucket_key(signing_key: str, kind: str, value: str) -> str:
    message = f"{kind}\0{value}".encode("utf-8")
    return hmac.new(signing_key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _increment_bucket(db: Session, key: str, now: datetime, window_seconds: int) -> tuple[datetime, int]:
    reset_before = now - timedelta(seconds=window_seconds)
    expired = LoginRateLimitBucket.window_started_at <= reset_before
    values = {"bucket_key": key, "window_started_at": now, "attempt_count": 1}
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = postgres_insert(LoginRateLimitBucket).values(**values)
    elif dialect == "sqlite":
        statement = sqlite_insert(LoginRateLimitBucket).values(**values)
    else:
        raise RuntimeError("Shared login rate limiting requires PostgreSQL or SQLite")
    statement = statement.on_conflict_do_update(
        index_elements=[LoginRateLimitBucket.bucket_key],
        set_={
            "window_started_at": case((expired, now), else_=LoginRateLimitBucket.window_started_at),
            "attempt_count": case((expired, 1), else_=LoginRateLimitBucket.attempt_count + 1),
        },
    ).returning(LoginRateLimitBucket.window_started_at, LoginRateLimitBucket.attempt_count)
    window_started_at, attempt_count = db.execute(statement).one()
    if window_started_at.tzinfo is None:
        window_started_at = window_started_at.replace(tzinfo=timezone.utc)
    return window_started_at, attempt_count


def record_login_attempt(
    db: Session,
    *,
    client_host: str,
    email: str,
    settings: Settings,
    now: datetime | None = None,
) -> int | None:
    """Atomically consume shared IP and account buckets; return Retry-After if blocked."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    window = settings.login_rate_limit_window_seconds
    # Expired rows are not needed after one day. The indexed prune bounds table growth
    # without relying on an in-process counter or cleanup worker.
    db.execute(delete(LoginRateLimitBucket).where(
        LoginRateLimitBucket.window_started_at < now - timedelta(days=1)
    ))
    key = settings.signing_key()
    keys = (
        _bucket_key(key, "ip", client_host or "unknown"),
        _bucket_key(key, "email", email.strip().lower()),
    )
    results = [_increment_bucket(db, item, now, window) for item in keys]
    db.commit()
    retry_after = [
        max(1, math.ceil((started + timedelta(seconds=window) - now).total_seconds()))
        for started, count in results
        if count > settings.login_rate_limit_attempts
    ]
    return max(retry_after) if retry_after else None
