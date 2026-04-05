import json
from pathlib import Path

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models.alert import Alert
from app.models.camera import Camera
from app.models.rule import Rule
from app.models.site import Site
from app.models.zone import Zone
from app.schemas.monitoring import (
    AlertRead,
    CameraCreate,
    CameraRead,
    DashboardOverview,
    LiveMonitorStatus,
    ModeTemplate,
    RuleCreate,
    RuleRead,
    SiteCreate,
    SiteRead,
    ZoneCreate,
    ZoneRead,
)
from app.services.monitoring_service import (
    build_dashboard_overview,
    create_site_with_default_rules,
    list_mode_templates,
)

router = APIRouter()
live_dir = Path(__file__).resolve().parents[5] / "storage" / "live"
live_status_path = live_dir / "status.json"
live_frame_path = live_dir / "latest_frame.jpg"


@router.get("/modes/templates", response_model=list[ModeTemplate])
def get_mode_templates(_: object = Depends(require_admin)) -> list[ModeTemplate]:
    return list_mode_templates()


@router.get("/sites", response_model=list[SiteRead])
def list_sites(db: Session = Depends(get_db), _: object = Depends(require_admin)) -> list[Site]:
    return list(db.scalars(select(Site).order_by(Site.created_at.desc())))


@router.post("/sites", response_model=SiteRead, status_code=status.HTTP_201_CREATED)
def create_site(
    payload: SiteCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Site:
    return create_site_with_default_rules(db, payload)


@router.get("/cameras", response_model=list[CameraRead])
def list_cameras(
    site_id: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[Camera]:
    statement = select(Camera).order_by(Camera.created_at.desc())
    if site_id:
        statement = statement.where(Camera.site_id == site_id)
    return list(db.scalars(statement))


@router.post("/cameras", response_model=CameraRead, status_code=status.HTTP_201_CREATED)
def create_camera(
    payload: CameraCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Camera:
    camera = Camera(**payload.model_dump(mode="python"))
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.get("/zones", response_model=list[ZoneRead])
def list_zones(
    site_id: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[Zone]:
    statement = select(Zone).order_by(Zone.created_at.desc())
    if site_id:
        statement = statement.where(Zone.site_id == site_id)
    return list(db.scalars(statement))


@router.post("/zones", response_model=ZoneRead, status_code=status.HTTP_201_CREATED)
def create_zone(
    payload: ZoneCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Zone:
    zone = Zone(**payload.model_dump(mode="python"))
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.get("/rules", response_model=list[RuleRead])
def list_rules(
    site_id: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[Rule]:
    statement = select(Rule).order_by(Rule.created_at.desc())
    if site_id:
        statement = statement.where(Rule.site_id == site_id)
    return list(db.scalars(statement))


@router.post("/rules", response_model=RuleRead, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: RuleCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Rule:
    rule = Rule(**payload.model_dump(mode="python"))
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/alerts", response_model=list[AlertRead])
def list_alerts(
    site_id: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[Alert]:
    statement = select(Alert).order_by(Alert.occurred_at.desc())
    if site_id:
        statement = statement.where(Alert.site_id == site_id)
    return list(db.scalars(statement.limit(100)))


@router.get("/dashboard/overview", response_model=DashboardOverview)
def get_dashboard_overview(
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> DashboardOverview:
    return build_dashboard_overview(db)


@router.get("/live/status", response_model=LiveMonitorStatus)
def get_live_status(_: object = Depends(require_admin)) -> LiveMonitorStatus:
    live_dir.mkdir(parents=True, exist_ok=True)

    payload: dict[str, object] = {
        "message": "Worker preview is not available yet.",
        "camera_connected": False,
    }
    if live_status_path.exists():
        payload.update(json.loads(live_status_path.read_text(encoding="utf-8")))

    if live_frame_path.exists():
        payload["frame_url"] = "/live-media/latest_frame.jpg"

    return LiveMonitorStatus(**payload)
