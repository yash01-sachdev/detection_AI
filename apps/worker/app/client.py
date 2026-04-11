import httpx

from app.config import Settings
from app.types import (
    Detection,
    EmployeeDefinition,
    KnownPersonDefinition,
    WorkerAssignmentDefinition,
    ZoneDefinition,
)


class ApiClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.runtime_assignment: WorkerAssignmentDefinition | None = None

    def set_runtime_assignment(self, assignment: WorkerAssignmentDefinition | None) -> None:
        self.runtime_assignment = assignment

    def get_runtime_assignment(self) -> WorkerAssignmentDefinition | None:
        return self.runtime_assignment

    def build_fallback_assignment(self) -> WorkerAssignmentDefinition | None:
        if not self.settings.site_id or not self.settings.camera_id:
            return None
        return WorkerAssignmentDefinition(
            worker_name=self.settings.worker_name,
            site_id=self.settings.site_id,
            camera_id=self.settings.camera_id,
            camera_source_type=self.settings.camera_source_type,
            camera_source=self.settings.camera_source,
            is_active=True,
            assignment_version=1,
        )

    def fetch_worker_assignment(self) -> WorkerAssignmentDefinition | None:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{self.settings.api_base_url}/ingest/workers/{self.settings.worker_name}/assignment",
                headers={"x-internal-token": self.settings.api_internal_token},
            )
            response.raise_for_status()

        payload = response.json()
        if not payload:
            return None
        return WorkerAssignmentDefinition.model_validate(payload)

    def fetch_zones(self) -> list[ZoneDefinition]:
        assignment = self.runtime_assignment
        if assignment is None or not assignment.site_id:
            return []

        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{self.settings.api_base_url}/ingest/sites/{assignment.site_id}/zones",
                headers={"x-internal-token": self.settings.api_internal_token},
            )
            response.raise_for_status()

        return [ZoneDefinition.model_validate(item) for item in response.json()]

    def fetch_employees(self) -> list[EmployeeDefinition]:
        assignment = self.runtime_assignment
        if assignment is None or not assignment.site_id:
            return []

        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                f"{self.settings.api_base_url}/ingest/sites/{assignment.site_id}/employees",
                headers={"x-internal-token": self.settings.api_internal_token},
            )
            response.raise_for_status()

        return [EmployeeDefinition.model_validate(item) for item in response.json()]

    def fetch_known_people(self) -> list[KnownPersonDefinition]:
        assignment = self.runtime_assignment
        if assignment is None or not assignment.site_id:
            return []

        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                f"{self.settings.api_base_url}/ingest/sites/{assignment.site_id}/known-people",
                headers={"x-internal-token": self.settings.api_internal_token},
            )
            response.raise_for_status()

        return [KnownPersonDefinition.model_validate(item) for item in response.json()]

    def ingest_detection(self, detection: Detection, snapshot_path: str | None = None) -> None:
        assignment = self.runtime_assignment
        if assignment is None or not assignment.site_id or not assignment.camera_id:
            return

        payload = {
            "site_id": assignment.site_id,
            "camera_id": assignment.camera_id,
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

    def publish_worker_status(
        self,
        *,
        camera_connected: bool,
        camera_source_type: str,
        camera_source: str,
        frame_count: int,
        last_detection_count: int,
        last_labels: list[str],
        message: str,
    ) -> None:
        assignment = self.runtime_assignment
        if assignment is None:
            return

        payload = {
            "assignment_version": assignment.assignment_version,
            "camera_connected": camera_connected,
            "camera_source_type": camera_source_type,
            "camera_source": camera_source,
            "frame_count": frame_count,
            "last_detection_count": last_detection_count,
            "last_labels": last_labels,
            "message": message,
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{self.settings.api_base_url}/ingest/workers/{self.settings.worker_name}/status",
                headers={"x-internal-token": self.settings.api_internal_token},
                json=payload,
            )
            response.raise_for_status()

    def upload_live_frame(self, frame_path: str) -> str | None:
        assignment = self.runtime_assignment
        if assignment is None:
            return None

        with open(frame_path, "rb") as handle:
            files = {"file": ("latest_frame.jpg", handle, "image/jpeg")}
            data = {"assignment_version": str(assignment.assignment_version)}
            with httpx.Client(timeout=20.0) as client:
                response = client.post(
                    f"{self.settings.api_base_url}/ingest/workers/{self.settings.worker_name}/live-frame",
                    headers={"x-internal-token": self.settings.api_internal_token},
                    files=files,
                    data=data,
                )
                response.raise_for_status()

        return str(response.json().get("path") or "")

    def upload_snapshot(self, snapshot_path: str) -> str | None:
        assignment = self.runtime_assignment
        if assignment is None:
            return None

        file_name = snapshot_path.split("/")[-1].split("\\")[-1] or "snapshot.jpg"
        with open(snapshot_path, "rb") as handle:
            files = {"file": (file_name, handle, "image/jpeg")}
            data = {"assignment_version": str(assignment.assignment_version)}
            with httpx.Client(timeout=20.0) as client:
                response = client.post(
                    f"{self.settings.api_base_url}/ingest/workers/{self.settings.worker_name}/snapshots",
                    headers={"x-internal-token": self.settings.api_internal_token},
                    files=files,
                    data=data,
                )
                response.raise_for_status()

        return str(response.json().get("path") or "")
