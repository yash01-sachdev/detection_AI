import httpx

from app.config import Settings
from app.types import Detection, ZoneDefinition


class ApiClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def fetch_zones(self) -> list[ZoneDefinition]:
        if not self.settings.site_id:
            return []

        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{self.settings.api_base_url}/ingest/sites/{self.settings.site_id}/zones",
                headers={"x-internal-token": self.settings.api_internal_token},
            )
            response.raise_for_status()

        return [ZoneDefinition.model_validate(item) for item in response.json()]

    def ingest_detection(self, detection: Detection, snapshot_path: str | None = None) -> None:
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
            "snapshot_path": snapshot_path,
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
