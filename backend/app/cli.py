import argparse
from getpass import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.models.user import User


def create_initial_admin(email: str) -> None:
    normalized_email = email.strip().lower()
    password = getpass("Initial administrator password (minimum 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    with get_session_factory()() as db:
        if db.scalar(select(User.id).where(User.role == "admin").limit(1)) is not None:
            raise SystemExit("An administrator already exists; use the protected admin API to add accounts")
        if db.scalar(select(User.id).where(User.email == normalized_email)) is not None:
            raise SystemExit("An account with this email already exists")
        db.add(User(email=normalized_email, password_hash=hash_password(password), role="admin"))
        db.commit()
    print(f"Initial administrator created: {normalized_email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Local backend administration commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    admin_parser = subparsers.add_parser("create-admin", help="Create the first administrator account")
    admin_parser.add_argument("--email", required=True)
    args = parser.parse_args()
    if args.command == "create-admin":
        create_initial_admin(args.email)


if __name__ == "__main__":
    main()
