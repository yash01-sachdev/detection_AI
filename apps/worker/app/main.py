import logging

from app.camera import build_camera_source
from app.client import ApiClient
from app.config import get_settings
from app.detection import build_detector
from app.face import build_face_recognizer
from app.pipeline import MonitoringPipeline
from app.posture import build_posture_analyzer


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    api_client = ApiClient(settings)

    pipeline = MonitoringPipeline(
        source=build_camera_source(settings),
        detector=build_detector(settings),
        api_client=api_client,
        frame_stride=settings.frame_stride,
        alert_cooldown_seconds=settings.alert_cooldown_seconds,
        worker_name=settings.worker_name,
        camera_source_type=settings.camera_source_type,
        camera_source=settings.camera_source,
        preview_output_dir=settings.preview_output_dir,
        snapshot_output_dir=settings.snapshot_output_dir,
        face_recognizer=build_face_recognizer(settings, api_client),
        posture_analyzer=build_posture_analyzer(
            inactivity_threshold_seconds=settings.inactivity_threshold_seconds,
            movement_threshold_px=settings.inactivity_movement_threshold_px,
        ),
    )
    pipeline.run()


if __name__ == "__main__":
    main()
