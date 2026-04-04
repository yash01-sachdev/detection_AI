from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_internal_token
from app.schemas.monitoring import DetectionIngestRequest, DetectionIngestResponse
from app.services.monitoring_service import ingest_detection_event

router = APIRouter()


@router.post("/events", response_model=DetectionIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_event(
    payload: DetectionIngestRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_token),
) -> DetectionIngestResponse:
    return ingest_detection_event(db, payload)
