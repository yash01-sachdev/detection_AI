from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import (
    Alert,
    Camera,
    Employee,
    EmployeeFaceProfile,
    Event,
    KnownPerson,
    KnownPersonFaceProfile,
    Rule,
    Site,
    User,
    WorkerAssignment,
    Zone,
)
from app.services.auth_service import bootstrap_default_admin

settings = get_settings()
live_media_dir = Path(__file__).resolve().parents[3] / "storage" / "live"
live_media_dir.mkdir(parents=True, exist_ok=True)
media_dir = Path(__file__).resolve().parents[3] / "storage"
media_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_employee_shift_columns()
    _remove_legacy_fall_rules()
    with SessionLocal() as db:
        bootstrap_default_admin(db)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
app.mount("/live-media", StaticFiles(directory=live_media_dir), name="live-media")
app.mount("/media", StaticFiles(directory=media_dir), name="media")


def _ensure_employee_shift_columns() -> None:
    inspector = inspect(engine)
    if "employees" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("employees")}
    statements = {
        "shift_name": "ALTER TABLE employees ADD COLUMN shift_name VARCHAR(120) NOT NULL DEFAULT 'Day Shift'",
        "shift_start_time": "ALTER TABLE employees ADD COLUMN shift_start_time VARCHAR(5) NOT NULL DEFAULT '09:00'",
        "shift_end_time": "ALTER TABLE employees ADD COLUMN shift_end_time VARCHAR(5) NOT NULL DEFAULT '17:00'",
        "shift_grace_minutes": "ALTER TABLE employees ADD COLUMN shift_grace_minutes INTEGER NOT NULL DEFAULT 10",
        "shift_days": "ALTER TABLE employees ADD COLUMN shift_days VARCHAR(64) NOT NULL DEFAULT 'mon,tue,wed,thu,fri'",
    }

    pending = [sql for column_name, sql in statements.items() if column_name not in existing_columns]
    if not pending:
        return

    with engine.begin() as connection:
        for statement in pending:
            connection.execute(text(statement))


def _remove_legacy_fall_rules() -> None:
    inspector = inspect(engine)
    if "rules" not in inspector.get_table_names():
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                DELETE FROM rules
                WHERE template_key = 'office_fall_detection'
                   OR conditions LIKE '%"posture": "fallen"%'
                   OR conditions LIKE '%"posture":"fallen"%'
                """
            )
        )
