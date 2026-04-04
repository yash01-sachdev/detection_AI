import httpx

from app.config import Settings
from app.types import Detection


class ApiClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def ingest_detection(self, detection: Detection) -> None:
        if not self.settings.site_id or not self.settings.camera_id:
            return

        payload = {
            "site_id": self.settings.site_id,
            "camera_id": self.settings.camera_id,
            "zone_id": detection.zone_id,
            "entity_type": detection.entity_type,
            "label": detection.identity or detection.label,
            "track_id": detection.track_id,
            "confidence": detection.confidence,
            "details": {
                "bbox": detection.bbox.model_dump(),
                "identity": detection.identity,
                "posture": detection.posture,
                **detection.details,
            },
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{self.settings.api_base_url}/ingest/events",
                headers={"x-internal-token": self.settings.api_internal_token},
                json=payload,
            )
            response.raise_for_status()

