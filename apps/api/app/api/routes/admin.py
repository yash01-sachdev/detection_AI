import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models.alert import Alert
from app.models.camera import Camera
from app.models.employee import Employee, EmployeeFaceProfile
from app.models.known_person import KnownPerson, KnownPersonFaceProfile
from app.models.rule import Rule
from app.models.site import Site
from app.models.user import User
from app.models.zone import Zone
from app.schemas.monitoring import (
    AlertRead,
    CameraCreate,
    CameraRead,
    DashboardOverview,
    EmployeeCreate,
    EmployeeFaceProfileRead,
    EmployeeReportRead,
    EmployeeRead,
    KnownPersonCreate,
    KnownPersonFaceProfileRead,
    KnownPersonRead,
    LiveMonitorStatus,
    ModeTemplate,
    RuleCreate,
    RuleRead,
    SiteCreate,
    SiteRead,
    WorkerAssignmentRead,
    WorkerAssignmentUpdate,
    ZoneCreate,
    ZoneRead,
)
from app.schemas.auth import AdminCreateRequest, UserRead
from app.services.known_person_service import (
    add_known_person_face_profile,
    create_known_person,
    delete_known_person,
    list_known_people,
)
from app.services.auth_service import create_admin_user, list_admin_users
from app.services.employee_report_service import build_employee_report
from app.services.employee_service import (
    add_employee_face_profile,
    create_employee,
    delete_employee,
    list_employees,
)
from app.services.monitoring_service import (
    build_dashboard_overview,
    create_site_with_default_rules,
    list_mode_templates,
)
from app.services.worker_service import build_live_status, list_worker_assignments, upsert_worker_assignment

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


@router.get("/admins", response_model=list[UserRead])
def get_admin_users(
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[User]:
    return list_admin_users(db)


@router.post("/admins", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def post_admin_user(
    payload: AdminCreateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> User:
    return create_admin_user(db, payload)


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


@router.get("/employees", response_model=list[EmployeeRead])
def get_employees(
    site_id: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[Employee]:
    return list_employees(db, site_id=site_id)


@router.post("/employees", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
def post_employee(
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Employee:
    return create_employee(db, payload)


@router.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee_route(
    employee_id: str,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> None:
    delete_employee(db, employee_id)


@router.get("/employees/{employee_id}/report", response_model=EmployeeReportRead)
def get_employee_report(
    employee_id: str,
    days: int = 7,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> EmployeeReportRead:
    return build_employee_report(db, employee_id, days)


@router.post(
    "/employees/{employee_id}/face-profiles",
    response_model=EmployeeFaceProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_employee_face_profile(
    employee_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> EmployeeFaceProfile:
    return await add_employee_face_profile(db, employee_id, file)


@router.get("/known-people", response_model=list[KnownPersonRead])
def get_known_people(
    site_id: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[KnownPerson]:
    return list_known_people(db, site_id=site_id)


@router.post("/known-people", response_model=KnownPersonRead, status_code=status.HTTP_201_CREATED)
def post_known_person(
    payload: KnownPersonCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> KnownPerson:
    return create_known_person(db, payload)


@router.delete("/known-people/{known_person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_known_person_route(
    known_person_id: str,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> None:
    delete_known_person(db, known_person_id)


@router.post(
    "/known-people/{known_person_id}/face-profiles",
    response_model=KnownPersonFaceProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_known_person_face_profile(
    known_person_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> KnownPersonFaceProfile:
    return await add_known_person_face_profile(db, known_person_id, file)


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


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_zone(
    zone_id: str,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> None:
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found.")

    db.delete(zone)
    db.commit()


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
    site_id: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> DashboardOverview:
    return build_dashboard_overview(db, site_id=site_id)


@router.get("/worker-assignments", response_model=list[WorkerAssignmentRead])
def get_worker_assignments(
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> list[WorkerAssignmentRead]:
    return list_worker_assignments(db)


@router.put("/worker-assignments/{worker_name}", response_model=WorkerAssignmentRead)
def put_worker_assignment(
    worker_name: str,
    payload: WorkerAssignmentUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> WorkerAssignmentRead:
    try:
        return upsert_worker_assignment(db, worker_name, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/live/status", response_model=LiveMonitorStatus)
def get_live_status(
    site_id: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> LiveMonitorStatus:
    live_status = build_live_status(db, site_id=site_id)
    if site_id or live_status.worker_name:
        return live_status

    payload: dict[str, object] = {
        "message": "Worker preview is not available yet.",
        "camera_connected": False,
    }
    if live_status_path.exists():
        payload.update(json.loads(live_status_path.read_text(encoding="utf-8")))

    if live_frame_path.exists():
        payload["frame_url"] = "/live-media/latest_frame.jpg"

    return LiveMonitorStatus(**payload)
