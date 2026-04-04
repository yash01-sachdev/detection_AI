import logging
from typing import Any

from app.camera import BaseCameraSource
from app.client import ApiClient
from app.detection import BaseDetector
from app.types import Detection

logger = logging.getLogger(__name__)


class SimpleFrameTracker:
    def __init__(self) -> None:
        self.frame_index = 0

    def assign_tracks(self, detections: list[Detection]) -> list[Detection]:
        self.frame_index += 1
        return [
            detection.model_copy(update={"track_id": f"f{self.frame_index}-d{index}"})
            for index, detection in enumerate(detections, start=1)
        ]


class NoopFaceRecognizer:
    def annotate(self, frame: Any, detections: list[Detection]) -> list[Detection]:
        return detections


class NoopPostureAnalyzer:
    def annotate(self, frame: Any, detections: list[Detection]) -> list[Detection]:
        return detections


class MonitoringPipeline:
    def __init__(
        self,
        source: BaseCameraSource,
        detector: BaseDetector,
        api_client: ApiClient,
        frame_stride: int,
    ) -> None:
        self.source = source
        self.detector = detector
        self.api_client = api_client
        self.frame_stride = max(frame_stride, 1)
        self.tracker = SimpleFrameTracker()
        self.face_recognizer = NoopFaceRecognizer()
        self.posture_analyzer = NoopPostureAnalyzer()

    def run(self) -> None:
        frame_count = 0
        self.source.open()
        logger.info("Camera source opened. Starting monitoring loop.")

        try:
            while True:
                ok, frame = self.source.read()
                if not ok:
                    logger.warning("Unable to read frame from camera source.")
                    break

                frame_count += 1
                if frame_count % self.frame_stride != 0:
                    continue

                detections = self.detector.detect(frame)
                detections = self.tracker.assign_tracks(detections)
                detections = self.face_recognizer.annotate(frame, detections)
                detections = self.posture_analyzer.annotate(frame, detections)

                for detection in detections:
                    try:
                        self.api_client.ingest_detection(detection)
                    except Exception as exc:  # pragma: no cover
                        logger.warning("Failed to publish detection: %s", exc)

                if detections:
                    logger.info("Processed frame %s with %s detections.", frame_count, len(detections))
        finally:
            self.source.release()
            logger.info("Camera source released.")

