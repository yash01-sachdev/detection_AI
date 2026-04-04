from abc import ABC, abstractmethod
from typing import Any

from app.config import Settings
from app.types import BoundingBox, Detection

SUPPORTED_LABELS = {
    "person": "person",
    "dog": "dog",
    "car": "vehicle",
    "bus": "vehicle",
    "truck": "vehicle",
    "motorbike": "vehicle",
    "motorcycle": "vehicle",
}


class BaseDetector(ABC):
    @abstractmethod
    def detect(self, frame: Any) -> list[Detection]:
        raise NotImplementedError


class MockDetector(BaseDetector):
    def detect(self, frame: Any) -> list[Detection]:
        return []


class YoloDetector(BaseDetector):
    def __init__(self, model_name: str, confidence_threshold: float) -> None:
        from ultralytics import YOLO

        self.model = YOLO(model_name)
        self.confidence_threshold = confidence_threshold

    def detect(self, frame: Any) -> list[Detection]:
        detections: list[Detection] = []
        results = self.model(frame, verbose=False)
        for result in results:
            for box in result.boxes:
                class_index = int(box.cls[0].item())
                label = result.names[class_index]
                if label not in SUPPORTED_LABELS:
                    continue

                confidence = float(box.conf[0].item())
                if confidence < self.confidence_threshold:
                    continue

                x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
                detections.append(
                    Detection(
                        label=label,
                        entity_type=SUPPORTED_LABELS[label],
                        confidence=confidence,
                        bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    )
                )
        return detections


def build_detector(settings: Settings) -> BaseDetector:
    if settings.detector_type == "yolo":
        return YoloDetector(settings.yolo_model, settings.confidence_threshold)
    return MockDetector()

