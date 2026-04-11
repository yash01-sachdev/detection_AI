from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.camera import Camera
from app.models.site import Site
from app.models.worker_assignment import WorkerAssignment
from app.schemas.monitoring import LiveMonitorStatus, WorkerAssignmentRead, WorkerAssignmentUpdate, WorkerStatusUpdate

storage_root = Path(__file__).resolve().parents[4] / "storage"
live_root = storage_root / "live"
snapshot_root = storage_root / "snapshots"


def list_worker_assignments(db: Session) -> list[WorkerAssignmentRead]:
    assignments = list(
        db.scalars(
            select(WorkerAssignment)
            .options(joinedload(WorkerAssignment.site), joinedload(WorkerAssignment.camera))
            .order_by(WorkerAssignment.worker_name.asc())
        )
    )
    return [_serialize_assignment(assignment) for assignment in assignments]


def upsert_worker_assignment(
    db: Session,
    worker_name: str,
    payload: WorkerAssignmentUpdate,
) -> WorkerAssignmentRead:
    site = db.get(Site, payload.site_id) if payload.site_id else None
    camera = db.get(Camera, payload.camera_id) if payload.camera_id else None

    if payload.site_id and site is None:
        raise ValueError("Selected site does not exist.")
    if payload.camera_id and camera is None:
        raise ValueError("Selected camera does not exist.")
    if site is not None and camera is not None and camera.site_id != site.id:
        raise ValueError("Selected camera does not belong to the selected site.")

    assignment = db.scalar(
        select(WorkerAssignment)
        .where(WorkerAssignment.worker_name == worker_name)
        .options(joinedload(WorkerAssignment.site), joinedload(WorkerAssignment.camera))
    )
    if assignment is None:
        assignment = WorkerAssignment(worker_name=worker_name)
        db.add(assignment)
        db.flush()

    has_changed = (
        assignment.site_id != payload.site_id
        or assignment.camera_id != payload.camera_id
        or assignment.is_active != payload.is_active
    )

    assignment.site_id = site.id if site is not None else None
    assignment.camera_id = camera.id if camera is not None else None
    assignment.is_active = payload.is_active

    if has_changed:
        assignment.assignment_version += 1
        assignment.camera_connected = False
        assignment.reported_camera_source_type = ""
        assignment.reported_camera_source = ""
        assignment.frame_count = 0
        assignment.last_detection_count = 0
        assignment.last_labels = []
        assignment.message = "Waiting for worker to pick up the new assignment."
        assignment.frame_path = None
        assignment.frame_updated_at = None
        assignment.last_heartbeat_at = None

    db.commit()
    db.refresh(assignment)
    return _serialize_assignment(assignment)


def get_worker_assignment(db: Session, worker_name: str) -> WorkerAssignmentRead | None:
    assignment = db.scalar(
        select(WorkerAssignment)
        .where(WorkerAssignment.worker_name == worker_name)
        .options(joinedload(WorkerAssignment.site), joinedload(WorkerAssignment.camera))
    )
    if assignment is None:
        return None
    return _serialize_assignment(assignment)


def record_worker_status(
    db: Session,
    worker_name: str,
    payload: WorkerStatusUpdate,
) -> WorkerAssignmentRead:
    assignment = _require_worker_assignment(db, worker_name)
    _require_assignment_version(assignment, payload.assignment_version)

    assignment.camera_connected = payload.camera_connected
    assignment.reported_camera_source_type = payload.camera_source_type
    assignment.reported_camera_source = payload.camera_source
    assignment.frame_count = payload.frame_count
    assignment.last_detection_count = payload.last_detection_count
    assignment.last_labels = payload.last_labels
    assignment.message = payload.message
    assignment.frame_updated_at = payload.frame_updated_at
    assignment.last_heartbeat_at = datetime.now(UTC)

    db.commit()
    db.refresh(assignment)
    return _serialize_assignment(assignment)


def save_worker_live_frame(
    db: Session,
    worker_name: str,
    assignment_version: int,
    content: bytes,
) -> str:
    assignment = _require_worker_assignment(db, worker_name)
    _require_assignment_version(assignment, assignment_version)

    worker_dir = live_root / worker_name
    worker_dir.mkdir(parents=True, exist_ok=True)
    file_path = worker_dir / "latest_frame.jpg"
    file_path.write_bytes(content)

    assignment.frame_path = f"/live-media/{worker_name}/latest_frame.jpg"
    assignment.frame_updated_at = datetime.now(UTC)
    assignment.last_heartbeat_at = datetime.now(UTC)

    db.commit()
    return assignment.frame_path


def save_worker_snapshot(
    db: Session,
    worker_name: str,
    assignment_version: int,
    file_name: str,
    content: bytes,
) -> str:
    assignment = _require_worker_assignment(db, worker_name)
    _require_assignment_version(assignment, assignment_version)

    snapshot_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    safe_name = Path(file_name or "snapshot.jpg").name or "snapshot.jpg"
    target_name = f"{timestamp}-{worker_name}-{safe_name}"
    target_path = snapshot_root / target_name
    target_path.write_bytes(content)

    assignment.last_heartbeat_at = datetime.now(UTC)
    db.commit()
    return f"/media/snapshots/{target_name}"


def build_live_status(db: Session, site_id: str | None = None) -> LiveMonitorStatus:
    statement = (
        select(WorkerAssignment)
        .options(joinedload(WorkerAssignment.site), joinedload(WorkerAssignment.camera))
        .order_by(WorkerAssignment.last_heartbeat_at.is_(None), WorkerAssignment.last_heartbeat_at.desc(), WorkerAssignment.updated_at.desc())
    )
    if site_id:
        statement = statement.where(WorkerAssignment.site_id == site_id)

    assignment = db.scalar(statement)
    if assignment is None:
        return LiveMonitorStatus(
            message="Worker preview is not available yet.",
            camera_connected=False,
        )

    return LiveMonitorStatus(
        worker_name=assignment.worker_name,
        assignment_active=assignment.is_active,
        site_id=assignment.site_id,
        site_name=assignment.site.name if assignment.site is not None else None,
        camera_id=assignment.camera_id,
        camera_name=assignment.camera.name if assignment.camera is not None else None,
        camera_source_type=assignment.reported_camera_source_type
        or (assignment.camera.source_type.value if assignment.camera is not None else ""),
        camera_source=assignment.reported_camera_source
        or (assignment.camera.source_value if assignment.camera is not None else ""),
        camera_connected=assignment.camera_connected,
        frame_updated_at=assignment.frame_updated_at,
        last_heartbeat_at=assignment.last_heartbeat_at,
        frame_count=assignment.frame_count,
        last_detection_count=assignment.last_detection_count,
        last_labels=list(assignment.last_labels or []),
        message=assignment.message or "Waiting for worker status.",
        frame_url=assignment.frame_path,
    )


def _require_worker_assignment(db: Session, worker_name: str) -> WorkerAssignment:
    assignment = db.scalar(
        select(WorkerAssignment)
        .where(WorkerAssignment.worker_name == worker_name)
        .options(joinedload(WorkerAssignment.site), joinedload(WorkerAssignment.camera))
    )
    if assignment is None:
        raise ValueError("Worker assignment does not exist yet.")
    return assignment


def _require_assignment_version(assignment: WorkerAssignment, expected_version: int) -> None:
    if assignment.assignment_version != expected_version:
        raise ValueError("Worker assignment changed. Refresh the assignment before sending status.")


def _serialize_assignment(assignment: WorkerAssignment) -> WorkerAssignmentRead:
    return WorkerAssignmentRead(
        id=assignment.id,
        worker_name=assignment.worker_name,
        site_id=assignment.site_id,
        site_name=assignment.site.name if assignment.site is not None else None,
        site_type=assignment.site.site_type.value if assignment.site is not None else None,
        camera_id=assignment.camera_id,
        camera_name=assignment.camera.name if assignment.camera is not None else None,
        camera_source_type=assignment.reported_camera_source_type
        or (assignment.camera.source_type.value if assignment.camera is not None else ""),
        camera_source=assignment.reported_camera_source
        or (assignment.camera.source_value if assignment.camera is not None else ""),
        is_active=assignment.is_active,
        assignment_version=assignment.assignment_version,
        camera_connected=assignment.camera_connected,
        frame_count=assignment.frame_count,
        last_detection_count=assignment.last_detection_count,
        last_labels=list(assignment.last_labels or []),
        message=assignment.message or "",
        frame_url=assignment.frame_path,
        frame_updated_at=assignment.frame_updated_at,
        last_heartbeat_at=assignment.last_heartbeat_at,
    )
