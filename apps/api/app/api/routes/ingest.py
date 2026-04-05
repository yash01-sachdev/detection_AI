from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_internal_token
from app.models.employee import Employee
from app.models.zone import Zone
from app.schemas.monitoring import DetectionIngestRequest, DetectionIngestResponse, EmployeeRead, ZoneRead
from app.services.employee_service import list_employee_profiles_for_site
from app.services.monitoring_service import ingest_detection_event, list_site_zones

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


@router.post("/events", response_model=DetectionIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_event(
    payload: DetectionIngestRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_token),
) -> DetectionIngestResponse:
    return ingest_detection_event(db, payload)
