import unittest

from app.pose import PoseDetection, PoseKeypoint
from app.posture import PostureAnalyzer
from app.types import BoundingBox, Detection


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value

    def set(self, value: float) -> None:
        self.value = value


class FakePoseEstimator:
    def __init__(self) -> None:
        self.pose_detections: list[PoseDetection] = []

    def estimate(self, frame) -> list[PoseDetection]:
        return self.pose_detections


class PostureAnalyzerTests(unittest.TestCase):
    def test_marks_person_in_desk_zone_inactive_after_threshold(self) -> None:
        clock = FakeClock()
        analyzer = PostureAnalyzer(
            pose_estimator=FakePoseEstimator(),
            head_down_threshold_seconds=5,
            inactivity_threshold_seconds=10,
            movement_threshold_px=18,
            clock=clock.now,
        )

        first = Detection(
            label="person",
            entity_type="person",
            confidence=0.94,
            bbox=BoundingBox(x1=10, y1=10, x2=110, y2=210),
            track_id="t1",
            details={"zone_type": "desk", "zone_name": "Desk A"},
        )
        clock.set(0)
        initial = analyzer.annotate(None, [first])[0]

        clock.set(5)
        still_active = analyzer.annotate(None, [first])[0]

        clock.set(12)
        inactive = analyzer.annotate(None, [first])[0]

        self.assertIsNone(initial.posture)
        self.assertIsNone(still_active.posture)
        self.assertEqual(inactive.posture, "inactive")
        self.assertEqual(inactive.details["inactive_seconds"], 12)
        self.assertEqual(inactive.details["posture_source"], "movement_watch")

    def test_movement_resets_inactivity_state(self) -> None:
        clock = FakeClock()
        analyzer = PostureAnalyzer(
            pose_estimator=FakePoseEstimator(),
            head_down_threshold_seconds=5,
            inactivity_threshold_seconds=10,
            movement_threshold_px=18,
            clock=clock.now,
        )

        detection = Detection(
            label="person",
            entity_type="employee",
            confidence=0.96,
            bbox=BoundingBox(x1=20, y1=20, x2=120, y2=220),
            track_id="t2",
            details={"zone_type": "desk", "zone_name": "Desk B"},
        )

        clock.set(0)
        analyzer.annotate(None, [detection])
        clock.set(11)
        inactive = analyzer.annotate(None, [detection])[0]

        moved = detection.model_copy(
            update={"bbox": BoundingBox(x1=60, y1=20, x2=160, y2=220)}
        )
        clock.set(12)
        active_again = analyzer.annotate(None, [moved])[0]

        self.assertEqual(inactive.posture, "inactive")
        self.assertIsNone(active_again.posture)
        self.assertNotIn("inactive_seconds", active_again.details)

    def test_marks_head_down_after_pose_is_stable_in_desk_zone(self) -> None:
        clock = FakeClock()
        pose_estimator = FakePoseEstimator()
        analyzer = PostureAnalyzer(
            pose_estimator=pose_estimator,
            head_down_threshold_seconds=5,
            inactivity_threshold_seconds=15,
            movement_threshold_px=18,
            clock=clock.now,
        )

        detection = Detection(
            label="person",
            entity_type="employee",
            confidence=0.97,
            bbox=BoundingBox(x1=100, y1=50, x2=220, y2=290),
            track_id="t3",
            details={"zone_type": "desk", "zone_name": "Desk C"},
        )
        pose_estimator.pose_detections = [
            _build_pose_detection(
                bbox=BoundingBox(x1=102, y1=52, x2=218, y2=288),
                keypoints={
                    "nose": (160, 150),
                    "left_shoulder": (145, 145),
                    "right_shoulder": (177, 145),
                    "left_hip": (150, 220),
                    "right_hip": (180, 220),
                },
            )
        ]

        clock.set(0)
        candidate = analyzer.annotate(None, [detection])[0]
        clock.set(6)
        active = analyzer.annotate(None, [detection])[0]

        self.assertIsNone(candidate.posture)
        self.assertEqual(active.posture, "head_down")
        self.assertEqual(active.details["posture_source"], "pose_model")


def _build_pose_detection(
    *,
    bbox: BoundingBox,
    keypoints: dict[str, tuple[float, float]],
) -> PoseDetection:
    return PoseDetection(
        bbox=bbox,
        confidence=0.92,
        keypoints={
            name: PoseKeypoint(name=name, x=x, y=y, confidence=0.95)
            for name, (x, y) in keypoints.items()
        },
    )


if __name__ == "__main__":
    unittest.main()
