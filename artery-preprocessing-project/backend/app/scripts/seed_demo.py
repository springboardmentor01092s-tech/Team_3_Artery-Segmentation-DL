"""Insert clearly labeled synthetic demo data. Do not use real patient identifiers."""

from __future__ import annotations

import os

from PIL import Image

from app.core.config import BACKEND_DIR, get_settings
from app.core.permissions import UserRole
from app.database.session import SessionLocal, init_db
from sqlalchemy import select

from app.models.case import Case
from app.models.user import User
from app.repositories import users as user_repo
from app.security.passwords import hash_password


def ensure_sample_png() -> None:
    sample_dir = BACKEND_DIR.parent / "data" / "sample_images"
    sample_dir.mkdir(parents=True, exist_ok=True)
    path = sample_dir / "synthetic_vessel_like.png"
    if path.exists():
        return
    img = Image.new("L", (256, 256), color=20)
    pixels = img.load()
    for x in range(256):
        for y in range(110, 146):
            pixels[x, y] = 200
    img.save(path)


def main() -> None:
    password = os.environ.get("DEMO_PASSWORD")
    if not password:
        raise SystemExit("Set DEMO_PASSWORD to a local development password before seeding.")
    init_db()
    ensure_sample_png()
    db = SessionLocal()
    try:
        for email, name, role in [
            ("demo.radiologist@example.com", "Demo Radiologist", UserRole.RADIOLOGIST.value),
            ("demo.researcher@example.com", "Demo Researcher", UserRole.RESEARCHER.value),
            ("demo.scientist@example.com", "Demo Data Scientist", UserRole.DATA_SCIENTIST.value),
        ]:
            user = user_repo.get_by_email(db, email)
            if user is None:
                user = User(
                    full_name=name,
                    email=email,
                    password_hash=hash_password(password),
                    role=role,
                    is_active=True,
                )
                db.add(user)
                db.flush()
            existing_demo = db.scalar(
                select(Case).where(Case.owner_id == user.id, Case.case_identifier == f"DEMO-{role[:4].upper()}-001")
            )
            if existing_demo is None:
                db.add(
                    Case(
                        case_identifier=f"DEMO-{role[:4].upper()}-001",
                        patient_identifier="SYNTH-0001",
                        age=58,
                        gender="unspecified",
                        medical_history="Synthetic demo record. Not a real patient.",
                        risk_factors="Demo data only.",
                        clinical_notes="Labeled synthetic case for local demonstration.",
                        imaging_modality="CTA",
                        anatomical_region="coronary",
                        analysis_status="created",
                        owner_id=user.id,
                    )
                )
        db.commit()
        print("Demo users and synthetic cases created. Do not use these accounts outside local development.")
        print(f"Dataset directory: {get_settings().resolved_dataset_dir()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
