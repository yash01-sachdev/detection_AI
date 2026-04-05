from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.types import BoundingBox

KEYPOINT_NAMES = (
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)

MIN_KEYPOINT_CONFIDENCE = 0.35


@dataclass(frozen=True)
class PoseKeypoint:
    name: str
    x: float
    y: float
    confidence: float


@dataclass(frozen=True)
class PoseDetection:
    bbox: BoundingBox
    confidence: float
    keypoints: dict[str, PoseKeypoint]


class BasePoseEstimator(ABC):
    @abstractmethod
    def estimate(self, frame: Any) -> list[PoseDetection]:
        raise NotImplementedError


class NoopPoseEstimator(BasePoseEstimator):
    def estimate(self, frame: Any) -> list[PoseDetection]:
        return []


class YoloPoseEstimator(BasePoseEstimator):
    def __init__(self, model_name: str, confidence_threshold: float) -> None:
        from ultralytics import YOLO

        self.model = YOLO(model_name)
        self.confidence_threshold = confidence_threshold

    def estimate(self, frame: Any) -> list[PoseDetection]:
        detections: list[PoseDetection] = []
        results = self.model(frame, verbose=False)

        for result in results:
            if result.boxes is None or result.keypoints is None:
                continue

            boxes = result.boxes.xyxy.tolist()
            box_confidences = result.boxes.conf.tolist()
            keypoint_positions = result.keypoints.xy.tolist()
            keypoint_confidences = (
                result.keypoints.conf.tolist()
                if result.keypoints.conf is not None
                else [[1.0 for _ in points] for points in keypoint_positions]
            )

            for bbox_values, box_confidence, point_values, point_confidences in zip(
                boxes,
                box_confidences,
                keypoint_positions,
                keypoint_confidences,
                strict=False,
            ):
                confidence = float(box_confidence)
                if confidence < self.confidence_threshold:
                    continue

                keypoints = _build_keypoint_map(point_values, point_confidences)
                if not keypoints:
                    continue

                x1, y1, x2, y2 = [float(value) for value in bbox_values]
                detections.append(
                    PoseDetection(
                        bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                        confidence=confidence,
                        keypoints=keypoints,
                    )
                )

        return detections


def build_pose_estimator(settings: Settings) -> BasePoseEstimator:
    if not settings.enable_pose_posture:
        return NoopPoseEstimator()
    return YoloPoseEstimator(settings.pose_model, settings.pose_confidence_threshold)


def _build_keypoint_map(
    point_values: list[list[float]],
    point_confidences: list[float],
) -> dict[str, PoseKeypoint]:
    keypoints: dict[str, PoseKeypoint] = {}

    for index, name in enumerate(KEYPOINT_NAMES):
        if index >= len(point_values):
            break

        confidence = float(point_confidences[index]) if index < len(point_confidences) else 1.0
        x, y = [float(value) for value in point_values[index]]
        if confidence < MIN_KEYPOINT_CONFIDENCE:
            continue
        if x <= 0 and y <= 0:
            continue

        keypoints[name] = PoseKeypoint(name=name, x=x, y=y, confidence=confidence)

    return keypoints
