from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_internal_token
from app.models.employee import Employee
from app.models.known_person import KnownPerson
from app.models.zone import Zone
from app.schemas.monitoring import (
    DetectionIngestRequest,
    DetectionIngestResponse,
    EmployeeRead,
    KnownPersonRead,
    WorkerAssignmentRead,
    WorkerMediaUploadResponse,
    WorkerStatusUpdate,
    ZoneRead,
)
from app.services.employee_service import list_employee_profiles_for_site
from app.services.known_person_service import list_known_people_for_site
from app.services.monitoring_service import ingest_detection_event, list_site_zones
from app.services.worker_service import get_worker_assignment, record_worker_status, save_worker_live_frame, save_worker_snapshot

router = APIRouter()


@router.get("/sites/{site_id}/zones", response_model=list[ZoneRead])
def get_site_zones(
    site_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_token),
) -> list[Zone]:
    return list_site_zones(db, site_id)


@router.get("/sites/{site_id}/employees", response_model=list[EmployeeRead])
def get_site_employees(
    site_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_token),
) -> list[Employee]:
    return list_employee_profiles_for_site(db, site_id)


@router.get("/sites/{site_id}/known-people", response_model=list[KnownPersonRead])
def get_site_known_people(
    site_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_token),
) -> list[KnownPerson]:
    return list_known_people_for_site(db, site_id)


@router.get("/workers/{worker_name}/assignment", response_model=WorkerAssignmentRead | None)
def get_worker_assignment_route(
    worker_name: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_token),
) -> WorkerAssignmentRead | None:
    return get_worker_assignment(db, worker_name)


@router.post("/workers/{worker_name}/status", response_model=WorkerAssignmentRead)
def post_worker_status(
    worker_name: str,
    payload: WorkerStatusUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_token),
) -> WorkerAssignmentRead:
    try:
        return record_worker_status(db, worker_name, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/workers/{worker_name}/live-frame", response_model=WorkerMediaUploadResponse)
async def post_worker_live_frame(
    worker_name: str,
    assignment_version: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_token),
) -> WorkerMediaUploadResponse:
    try:
        path = save_worker_live_frame(
            db=db,
            worker_name=worker_name,
            assignment_version=assignment_version,
            content=await file.read(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return WorkerMediaUploadResponse(path=path)


@router.post("/workers/{worker_name}/snapshots", response_model=WorkerMediaUploadResponse)
async def post_worker_snapshot(
    worker_name: str,
    assignment_version: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_token),
) -> WorkerMediaUploadResponse:
    try:
        path = save_worker_snapshot(
            db=db,
            worker_name=worker_name,
            assignment_version=assignment_version,
            file_name=file.filename or "snapshot.jpg",
            content=await file.read(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return WorkerMediaUploadResponse(path=path)


@router.post("/events", response_model=DetectionIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_event(
    payload: DetectionIngestRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_token),
) -> DetectionIngestResponse:
    return ingest_detection_event(db, payload)
