import json

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def record_audit(
    db: Session,
    action: str,
    actor_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    safe_metadata = None
    if metadata:
        filtered = {k: v for k, v in metadata.items() if k.lower() not in {"password", "token", "secret", "jwt"}}
        safe_metadata = json.dumps(filtered, default=str)
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_json=safe_metadata,
        )
    )
