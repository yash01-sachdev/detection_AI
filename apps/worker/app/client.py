import httpx

from app.config import Settings
from app.types import Detection


class ApiClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def ingest_detection(self, detection: Detection) -> None:
        if not self.settings.site_id or not self.settings.camera_id:
            return

        subject = detection.identity or detection.label.replace("_", " ")
        confidence_pct = round(detection.confidence * 100)
        alert_title = f"{subject.title()} detected"
        alert_description = (
            f"Live worker detected {subject} on camera {self.settings.camera_id} "
            f"with {confidence_pct}% confidence."
        )

        payload = {
            "site_id": self.settings.site_id,
            "camera_id": self.settings.camera_id,
            "zone_id": detection.zone_id,
            "entity_type": detection.entity_type,
            "label": detection.identity or detection.label,
            "track_id": detection.track_id,
            "confidence": detection.confidence,
            "alert_title": alert_title,
            "alert_description": alert_description,
            "severity": "medium",
            "details": {
                "bbox": detection.bbox.model_dump(),
                "identity": detection.identity,
                "posture": detection.posture,
                "source": self.settings.worker_name,
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
