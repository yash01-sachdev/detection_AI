from fastapi import APIRouter

from app.api.routes import admin, auth, health, ingest

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
