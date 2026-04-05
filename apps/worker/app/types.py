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
