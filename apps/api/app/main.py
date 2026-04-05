from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import Alert, Camera, Employee, EmployeeFaceProfile, Event, Rule, Site, User, Zone
from app.services.auth_service import bootstrap_default_admin

settings = get_settings()
live_media_dir = Path(__file__).resolve().parents[3] / "storage" / "live"
live_media_dir.mkdir(parents=True, exist_ok=True)
media_dir = Path(__file__).resolve().parents[3] / "storage"
media_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
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
