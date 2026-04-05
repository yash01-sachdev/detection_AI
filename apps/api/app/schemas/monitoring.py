from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import CameraSourceType, EntityType, RuleSeverity, SiteType, ZoneType


class ModeRuleTemplate(BaseModel):
    template_key: str
    name: str
    description: str
    severity: str


class ModeTemplate(BaseModel):
    site_type: str
    label: str
    description: str
    rules: list[ModeRuleTemplate]


class SiteCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    site_type: SiteType
    timezone: str = "Asia/Calcutta"
    description: str = ""


class SiteRead(BaseModel):
    id: str
    name: str
    site_type: str
    timezone: str
    description: str
    is_active: bool

    model_config = {"from_attributes": True}


class CameraCreate(BaseModel):
    site_id: str
    name: str = Field(min_length=2, max_length=255)
    source_type: CameraSourceType
    source_value: str
    is_enabled: bool = True


class CameraRead(BaseModel):
    id: str
    site_id: str
    name: str
    source_type: str
    source_value: str
    is_enabled: bool

    model_config = {"from_attributes": True}


class ZonePoint(BaseModel):
    x: float
    y: float


class ZoneCreate(BaseModel):
    site_id: str
    name: str = Field(min_length=2, max_length=255)
    zone_type: ZoneType
    color: str = "#148A72"
    is_restricted: bool = False
    points: list[ZonePoint] = Field(default_factory=list)


class ZoneRead(BaseModel):
    id: str
    site_id: str
    name: str
    zone_type: str
    color: str
    is_restricted: bool
    points: list[ZonePoint]

    model_config = {"from_attributes": True}


class RuleCreate(BaseModel):
    site_id: str | None = None
    applies_to_site_type: SiteType | None = None
    template_key: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=255)
    description: str = ""
    conditions: dict[str, object] = Field(default_factory=dict)
    actions: dict[str, object] = Field(default_factory=dict)
    severity: RuleSeverity = RuleSeverity.medium
    is_default: bool = False
    is_enabled: bool = True


class RuleRead(BaseModel):
    id: str
    site_id: str | None
    applies_to_site_type: str | None
    template_key: str
    name: str
    description: str
    conditions: dict[str, object]
    actions: dict[str, object]
    severity: str
    is_default: bool
    is_enabled: bool

    model_config = {"from_attributes": True}


class AlertRead(BaseModel):
    id: str
    site_id: str
    camera_id: str | None
    rule_id: str | None
    event_id: str | None
    title: str
    description: str
    severity: str
    status: str
    snapshot_path: str | None
    occurred_at: datetime
    details: dict[str, object]

    model_config = {"from_attributes": True}


class DashboardStat(BaseModel):
    key: str
    label: str
    value: int


class DashboardOverview(BaseModel):
    stats: list[DashboardStat]
    recent_alerts: list[AlertRead]


class LiveMonitorStatus(BaseModel):
    worker_name: str = ""
    camera_source_type: str = ""
    camera_source: str = ""
    camera_connected: bool = False
    frame_updated_at: datetime | None = None
    frame_count: int = 0
    last_detection_count: int = 0
    last_labels: list[str] = Field(default_factory=list)
    message: str = ""
    frame_url: str | None = None


class DetectionIngestRequest(BaseModel):
    site_id: str
    camera_id: str
    zone_id: str | None = None
    entity_type: EntityType
    label: str
    track_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    occurred_at: datetime | None = None
    details: dict[str, object] = Field(default_factory=dict)
    alert_title: str | None = None
    alert_description: str | None = None
    severity: RuleSeverity = RuleSeverity.medium
    snapshot_path: str | None = None
    rule_id: str | None = None


class DetectionIngestResponse(BaseModel):
    event_id: str
    alert_id: str | None = None
