import atexit
import json
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from time import sleep

from app.camera import build_camera_source_from_values
from app.client import ApiClient
from app.config import get_settings
from app.detection import build_detector
from app.face import build_face_recognizer
from app.pipeline import MonitoringPipeline
from app.pose import build_pose_estimator
from app.posture import build_posture_analyzer


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_lock_payload(lock_path: Path) -> dict[str, object]:
    try:
        return json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


@contextmanager
def _single_instance_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()

    def cleanup() -> None:
        payload = _read_lock_payload(lock_path)
        if int(payload.get("pid", 0) or 0) == pid:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass

    try:
        file_descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        payload = _read_lock_payload(lock_path)
        existing_pid = int(payload.get("pid", 0) or 0)
        if _pid_is_running(existing_pid):
            raise RuntimeError(
                f"Worker already running with PID {existing_pid}. Stop it before starting another worker."
            )
        lock_path.unlink(missing_ok=True)
        file_descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)

    with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
        json.dump({"pid": pid}, handle)

    atexit.register(cleanup)
    try:
        yield
    finally:
        cleanup()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    lock_path = Path(settings.preview_output_dir).resolve() / "worker.lock"
    api_client = ApiClient(settings)

    with _single_instance_lock(lock_path):
        while True:
            assignment = _resolve_runtime_assignment(api_client)
            if assignment is None or not assignment.is_usable():
                logging.info("No active worker assignment yet. Waiting for API assignment.")
                api_client.set_runtime_assignment(None)
                sleep(settings.assignment_poll_seconds)
                continue

            api_client.set_runtime_assignment(assignment)
            logging.info(
                "Starting worker runtime for site %s on camera %s.",
                assignment.site_id,
                assignment.camera_id,
            )

            try:
                pipeline = MonitoringPipeline(
                    source=build_camera_source_from_values(
                        assignment.camera_source_type,
                        assignment.camera_source,
                    ),
                    detector=build_detector(settings),
                    api_client=api_client,
                    frame_stride=settings.frame_stride,
                    alert_cooldown_seconds=settings.alert_cooldown_seconds,
                    worker_name=settings.worker_name,
                    camera_source_type=assignment.camera_source_type,
                    camera_source=assignment.camera_source,
                    preview_output_dir=settings.preview_output_dir,
                    snapshot_output_dir=settings.snapshot_output_dir,
                    assignment_signature=assignment.signature(),
                    assignment_poll_seconds=settings.assignment_poll_seconds,
                    status_publish_seconds=settings.status_publish_seconds,
                    live_frame_upload_seconds=settings.live_frame_upload_seconds,
                    face_recognizer=build_face_recognizer(settings, api_client),
                    posture_analyzer=build_posture_analyzer(
                        pose_estimator=build_pose_estimator(settings),
                        head_down_threshold_seconds=settings.head_down_threshold_seconds,
                        inactivity_threshold_seconds=settings.inactivity_threshold_seconds,
                        movement_threshold_px=settings.inactivity_movement_threshold_px,
                    ),
                )
                pipeline.run(lambda: _resolve_runtime_assignment(api_client))
            except Exception as exc:  # pragma: no cover
                logging.exception("Worker runtime failed: %s", exc)
                sleep(2)


def _resolve_runtime_assignment(api_client: ApiClient):
    try:
        assignment = api_client.fetch_worker_assignment()
    except Exception as exc:  # pragma: no cover
        logging.warning("Unable to refresh worker assignment from API: %s", exc)
        return api_client.get_runtime_assignment() or api_client.build_fallback_assignment()

    if assignment is not None:
        return assignment
    return api_client.build_fallback_assignment()


if __name__ == "__main__":
    main()
