import httpx

from app.config import Settings
from app.types import Detection, EmployeeDefinition, ZoneDefinition


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

    def fetch_employees(self) -> list[EmployeeDefinition]:
        if not self.settings.site_id:
            return []

        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                f"{self.settings.api_base_url}/ingest/sites/{self.settings.site_id}/employees",
                headers={"x-internal-token": self.settings.api_internal_token},
            )
            response.raise_for_status()

        return [EmployeeDefinition.model_validate(item) for item in response.json()]

    def ingest_detection(self, detection: Detection, snapshot_path: str | None = None) -> None:
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
