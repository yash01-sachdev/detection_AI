import tempfile
import unittest

from app.pipeline import MonitoringPipeline, StableTracker
from app.types import BoundingBox, Detection, ZoneDefinition, ZonePoint


class DummySource:
    def open(self) -> None:
        return None

    def read(self):
        return False, None

    def release(self) -> None:
        return None


class DummyDetector:
    def detect(self, frame):
        return []


class DummyClient:
    def fetch_zones(self):
        return []

    def ingest_detection(self, detection, snapshot_path=None):
        return None


class PipelineTests(unittest.TestCase):
    def test_stable_tracker_reuses_track_for_nearby_detection(self) -> None:
        tracker = StableTracker()
        first = Detection(
            label="person",
            entity_type="person",
            confidence=0.95,
            bbox=BoundingBox(x1=10, y1=10, x2=110, y2=210),
        )
        second = Detection(
            label="person",
            entity_type="person",
            confidence=0.96,
            bbox=BoundingBox(x1=18, y1=16, x2=118, y2=216),
        )

        tracked_first = tracker.assign_tracks([first])[0]
        tracked_second = tracker.assign_tracks([second])[0]

        self.assertEqual(tracked_first.track_id, tracked_second.track_id)
        self.assertTrue(tracked_first.details["track_is_new"])
        self.assertFalse(tracked_second.details["track_is_new"])

    def test_zone_assignment_prefers_restricted_zone(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline = MonitoringPipeline(
                source=DummySource(),
                detector=DummyDetector(),
                api_client=DummyClient(),
                frame_stride=1,
                alert_cooldown_seconds=3,
                worker_name="unit-test-worker",
                camera_source_type="test",
                camera_source="test",
                preview_output_dir=temp_dir,
                snapshot_output_dir=temp_dir,
            )

            general_zone = ZoneDefinition(
                id="general-1",
                name="General",
                zone_type="general",
                color="#148A72",
                is_restricted=False,
                points=[
                    ZonePoint(x=0, y=0),
                    ZonePoint(x=640, y=0),
                    ZonePoint(x=640, y=480),
                    ZonePoint(x=0, y=480),
                ],
            )
            restricted_zone = ZoneDefinition(
                id="restricted-1",
                name="Restricted",
                zone_type="restricted",
                color="#ff0000",
                is_restricted=True,
                points=[
                    ZonePoint(x=120, y=80),
                    ZonePoint(x=520, y=80),
                    ZonePoint(x=520, y=420),
                    ZonePoint(x=120, y=420),
                ],
            )
            pipeline.zones = [general_zone, restricted_zone]

            detection = Detection(
                label="person",
                entity_type="person",
                confidence=0.94,
                bbox=BoundingBox(x1=200, y1=120, x2=300, y2=320),
            )

            assigned = pipeline._assign_zones([detection])[0]

        self.assertEqual(assigned.zone_id, "restricted-1")
        self.assertEqual(assigned.details["zone_name"], "Restricted")
        self.assertTrue(assigned.details["zone_restricted"])

    def test_publish_logic_sends_first_track_and_zone_entry_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline = MonitoringPipeline(
                source=DummySource(),
                detector=DummyDetector(),
                api_client=DummyClient(),
                frame_stride=1,
                alert_cooldown_seconds=3,
                worker_name="unit-test-worker",
                camera_source_type="test",
                camera_source="test",
                preview_output_dir=temp_dir,
                snapshot_output_dir=temp_dir,
            )

            first = Detection(
                label="person",
                entity_type="person",
                confidence=0.9,
                bbox=BoundingBox(x1=10, y1=10, x2=110, y2=210),
                track_id="t1",
                details={"track_is_new": True},
            )
            same_track = first.model_copy(update={"details": {"track_is_new": False}})
            zone_entry = same_track.model_copy(
                update={"zone_id": "zone-1", "details": {"track_is_new": False, "zone_name": "Restricted"}}
            )

            self.assertTrue(pipeline._should_publish(first))
            self.assertFalse(pipeline._should_publish(same_track))
            self.assertTrue(pipeline._should_publish(zone_entry))

    def test_publish_logic_sends_identity_upgrade_for_existing_track(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline = MonitoringPipeline(
                source=DummySource(),
                detector=DummyDetector(),
                api_client=DummyClient(),
                frame_stride=1,
                alert_cooldown_seconds=3,
                worker_name="unit-test-worker",
                camera_source_type="test",
                camera_source="test",
                preview_output_dir=temp_dir,
                snapshot_output_dir=temp_dir,
            )

            first = Detection(
                label="person",
                entity_type="person",
                confidence=0.9,
                bbox=BoundingBox(x1=10, y1=10, x2=110, y2=210),
                track_id="t1",
                details={"track_is_new": True},
            )
            upgraded = Detection(
                label="person",
                entity_type="employee",
                confidence=0.9,
                bbox=BoundingBox(x1=12, y1=10, x2=112, y2=210),
                track_id="t1",
                identity="Smoke Tester",
                details={
                    "track_is_new": False,
                    "employee_id": "employee-1",
                    "employee_code": "EMP-001",
                },
            )

            self.assertTrue(pipeline._should_publish(first))
            self.assertTrue(pipeline._should_publish(upgraded))
            self.assertFalse(pipeline._should_publish(upgraded))


if __name__ == "__main__":
    unittest.main()
