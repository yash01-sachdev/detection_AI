from datetime import UTC, datetime
from pathlib import Path
from re import sub
from shutil import rmtree

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.known_person import KnownPerson, KnownPersonFaceProfile
from app.schemas.monitoring import KnownPersonCreate

known_people_faces_dir = Path(__file__).resolve().parents[4] / "storage" / "known-people-faces"


def list_known_people(db: Session, site_id: str | None = None) -> list[KnownPerson]:
    statement = (
        select(KnownPerson)
        .options(selectinload(KnownPerson.face_profiles))
        .order_by(KnownPerson.created_at.desc())
    )
    if site_id:
        statement = statement.where(KnownPerson.site_id == site_id)
    return list(db.scalars(statement))


def list_known_people_for_site(db: Session, site_id: str) -> list[KnownPerson]:
    return list(
        db.scalars(
            select(KnownPerson)
            .options(selectinload(KnownPerson.face_profiles))
            .where(KnownPerson.site_id == site_id, KnownPerson.is_active.is_(True))
            .order_by(KnownPerson.created_at.asc())
        )
    )


def create_known_person(db: Session, payload: KnownPersonCreate) -> KnownPerson:
    known_person = KnownPerson(
        site_id=payload.site_id,
        display_name=payload.display_name,
        notes=payload.notes,
        is_active=payload.is_active,
    )
    db.add(known_person)
    db.commit()
    db.refresh(known_person)
    return known_person


async def add_known_person_face_profile(
    db: Session,
    known_person_id: str,
    uploaded_file: UploadFile,
) -> KnownPersonFaceProfile:
    known_person = db.get(KnownPerson, known_person_id)
    if known_person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Known person not found.",
        )

    content = await uploaded_file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image is empty.",
        )

    suffix = Path(uploaded_file.filename or "face.jpg").suffix.lower() or ".jpg"
    safe_name = sub(r"[^a-zA-Z0-9_-]+", "-", Path(uploaded_file.filename or "face").stem).strip("-") or "face"
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    person_dir = known_people_faces_dir / known_person_id
    person_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{timestamp}-{safe_name}{suffix}"
    file_path = person_dir / file_name
    file_path.write_bytes(content)

    profile = KnownPersonFaceProfile(
        known_person_id=known_person_id,
        source_image_path=f"/media/known-people-faces/{known_person_id}/{file_name}",
        embedding=None,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def delete_known_person(db: Session, known_person_id: str) -> None:
    known_person = db.scalar(
        select(KnownPerson)
        .options(selectinload(KnownPerson.face_profiles))
        .where(KnownPerson.id == known_person_id)
    )
    if known_person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Known person not found.",
        )

    person_dir = known_people_faces_dir / known_person.id
    for profile in list(known_person.face_profiles):
        db.delete(profile)
    db.delete(known_person)
    db.commit()

    rmtree(person_dir, ignore_errors=True)
