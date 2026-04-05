from datetime import UTC, datetime
from pathlib import Path
from re import sub

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.employee import Employee, EmployeeFaceProfile
from app.schemas.monitoring import EmployeeCreate

faces_dir = Path(__file__).resolve().parents[4] / "storage" / "faces"


def list_employees(db: Session, site_id: str | None = None) -> list[Employee]:
    statement = (
        select(Employee)
        .options(selectinload(Employee.face_profiles))
        .order_by(Employee.created_at.desc())
    )
    if site_id:
        statement = statement.where(Employee.site_id == site_id)
    return list(db.scalars(statement))


def list_employee_profiles_for_site(db: Session, site_id: str) -> list[Employee]:
    return list(
        db.scalars(
            select(Employee)
            .options(selectinload(Employee.face_profiles))
            .where(Employee.site_id == site_id, Employee.is_active.is_(True))
            .order_by(Employee.created_at.asc())
        )
    )


def create_employee(db: Session, payload: EmployeeCreate) -> Employee:
    existing = db.scalar(select(Employee).where(Employee.employee_code == payload.employee_code))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee code already exists.",
        )

    employee = Employee(**payload.model_dump(mode="python"))
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


async def add_employee_face_profile(
    db: Session,
    employee_id: str,
    uploaded_file: UploadFile,
) -> EmployeeFaceProfile:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
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
    employee_dir = faces_dir / employee_id
    employee_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{timestamp}-{safe_name}{suffix}"
    file_path = employee_dir / file_name
    file_path.write_bytes(content)

    profile = EmployeeFaceProfile(
        employee_id=employee_id,
        source_image_path=f"/media/faces/{employee_id}/{file_name}",
        embedding=None,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile
