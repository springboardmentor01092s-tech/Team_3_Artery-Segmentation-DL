"""Create the first administrator from environment variables or CLI arguments.

Example (PowerShell):
  $env:BOOTSTRAP_ADMIN_EMAIL="admin@example.com"
  $env:BOOTSTRAP_ADMIN_PASSWORD="use-a-strong-local-password"
  $env:BOOTSTRAP_ADMIN_NAME="Local Administrator"
  python -m app.scripts.create_admin
"""

from __future__ import annotations

import argparse
import os
import sys

from app.core.permissions import UserRole
from app.database.session import SessionLocal, init_db
from app.models.user import User
from app.repositories import users as user_repo
from app.security.passwords import hash_password
from app.utils.audit import record_audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a local administrator account.")
    parser.add_argument("--email", default=os.environ.get("BOOTSTRAP_ADMIN_EMAIL"))
    parser.add_argument("--password", default=os.environ.get("BOOTSTRAP_ADMIN_PASSWORD"))
    parser.add_argument("--name", default=os.environ.get("BOOTSTRAP_ADMIN_NAME", "Administrator"))
    args = parser.parse_args()
    if not args.email or not args.password:
        print("Provide --email and --password or set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD.", file=sys.stderr)
        return 1
    if len(args.password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 1

    init_db()
    db = SessionLocal()
    try:
        existing = user_repo.get_by_email(db, args.email)
        if existing:
            if existing.role != UserRole.ADMINISTRATOR.value:
                existing.role = UserRole.ADMINISTRATOR.value
                existing.is_active = True
                record_audit(db, "admin.bootstrap_promote", actor_id=existing.id, resource_type="user", resource_id=existing.id)
                db.commit()
                print(f"Existing user {existing.email} promoted to administrator.")
            else:
                print(f"Administrator {existing.email} already exists.")
            return 0
        user = User(
            full_name=args.name.strip() or "Administrator",
            email=args.email.lower(),
            password_hash=hash_password(args.password),
            role=UserRole.ADMINISTRATOR.value,
            is_active=True,
        )
        db.add(user)
        db.flush()
        record_audit(db, "admin.bootstrap_create", actor_id=user.id, resource_type="user", resource_id=user.id)
        db.commit()
        print(f"Administrator created: {user.email}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
