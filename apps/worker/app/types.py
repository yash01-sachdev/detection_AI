from datetime import UTC, datetime

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class ZonePoint(BaseModel):
    x: float
    y: float


class ZoneDefinition(BaseModel):
    id: str
    name: str
    zone_type: str
    color: str
    is_restricted: bool
    points: list[ZonePoint] = Field(default_factory=list)


class EmployeeFaceProfileDefinition(BaseModel):
    id: str
    employee_id: str
    source_image_path: str


class EmployeeDefinition(BaseModel):
    id: str
    site_id: str | None = None
    employee_code: str
    first_name: str
    last_name: str
    role_title: str
    is_active: bool
    face_profiles: list[EmployeeFaceProfileDefinition] = Field(default_factory=list)


class WorkerAssignmentDefinition(BaseModel):
    worker_name: str
    site_id: str | None = None
    site_name: str | None = None
    camera_id: str | None = None
    camera_name: str | None = None
    camera_source_type: str = ""
    camera_source: str = ""
    is_active: bool = True
    assignment_version: int = 0

    def signature(self) -> str:
        return (
            f"{self.worker_name}:{self.assignment_version}:{self.site_id or ''}:"
            f"{self.camera_id or ''}:{self.camera_source_type}:{self.camera_source}:{int(self.is_active)}"
        )

    def is_usable(self) -> bool:
        return bool(
            self.is_active
            and self.site_id
            and self.camera_id
            and self.camera_source_type
            and self.camera_source
        )


class Detection(BaseModel):
    label: str
    entity_type: str
    confidence: float = Field(ge=0, le=1)
    bbox: BoundingBox
    track_id: str | None = None
    identity: str | None = None
    posture: str | None = None
    zone_id: str | None = None
    details: dict[str, object] = Field(default_factory=dict)


class FrameAnalysis(BaseModel):
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    detections: list[Detection] = Field(default_factory=list)
