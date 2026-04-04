import logging

from app.camera import build_camera_source
from app.client import ApiClient
from app.config import get_settings
from app.detection import build_detector
from app.pipeline import MonitoringPipeline


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()

    pipeline = MonitoringPipeline(
        source=build_camera_source(settings),
        detector=build_detector(settings),
        api_client=ApiClient(settings),
        frame_stride=settings.frame_stride,
        alert_cooldown_seconds=settings.alert_cooldown_seconds,
    )
    pipeline.run()


if __name__ == "__main__":
    main()
