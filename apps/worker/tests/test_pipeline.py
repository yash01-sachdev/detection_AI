import tempfile
import unittest

from app.pipeline import MonitoringPipeline, StableTracker, _deduplicate_detections
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

    def test_publish_logic_uses_presence_key_to_avoid_repeat_zone_entry(self) -> None:
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

            first_entry = Detection(
                label="person",
                entity_type="employee",
                confidence=0.9,
                bbox=BoundingBox(x1=10, y1=10, x2=110, y2=210),
                track_id="t1",
                identity="Demo User",
                zone_id="zone-1",
                details={
                    "track_is_new": True,
                    "employee_id": "employee-1",
                    "presence_key": "p1",
                    "presence_is_new": True,
                },
            )
            same_presence_new_track = first_entry.model_copy(
                update={
                    "track_id": "t2",
                    "details": {
                        "track_is_new": True,
                        "employee_id": "employee-1",
                        "presence_key": "p1",
                        "presence_is_new": False,
                    },
                }
            )
            returned_after_exit = first_entry.model_copy(
                update={
                    "track_id": "t3",
                    "details": {
                        "track_is_new": True,
                        "employee_id": "employee-1",
                        "presence_key": "p2",
                        "presence_is_new": True,
                    },
                }
            )

            self.assertTrue(pipeline._should_publish(first_entry))
            self.assertFalse(pipeline._should_publish(same_presence_new_track))
            self.assertTrue(pipeline._should_publish(returned_after_exit))

    def test_publish_logic_sends_inactivity_transition_once_until_reset(self) -> None:
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
                entity_type="employee",
                confidence=0.92,
                bbox=BoundingBox(x1=10, y1=10, x2=110, y2=210),
                track_id="t1",
                details={"track_is_new": True, "employee_id": "employee-1"},
            )
            inactive = first.model_copy(
                update={
                    "posture": "inactive",
                    "details": {
                        "track_is_new": False,
                        "employee_id": "employee-1",
                        "inactive_seconds": 24,
                    },
                }
            )
            resumed = first.model_copy(
                update={
                    "details": {
                        "track_is_new": False,
                        "employee_id": "employee-1",
                    }
                }
            )

            self.assertTrue(pipeline._should_publish(first))
            self.assertTrue(pipeline._should_publish(inactive))
            self.assertFalse(pipeline._should_publish(inactive))
            self.assertFalse(pipeline._should_publish(resumed))
            self.assertTrue(pipeline._should_publish(inactive))

    def test_deduplicate_detections_keeps_recognized_employee_over_generic_people(self) -> None:
        employee = Detection(
            label="person",
            entity_type="employee",
            confidence=0.78,
            bbox=BoundingBox(x1=100, y1=60, x2=340, y2=430),
            track_id="t2",
            identity="Demo User",
            details={"employee_id": "employee-1"},
        )
        generic_overlap = Detection(
            label="person",
            entity_type="person",
            confidence=0.85,
            bbox=BoundingBox(x1=110, y1=70, x2=330, y2=420),
            track_id="t1",
        )
        generic_second_overlap = Detection(
            label="person",
            entity_type="person",
            confidence=0.65,
            bbox=BoundingBox(x1=95, y1=50, x2=345, y2=435),
            track_id="t3",
        )

        deduplicated = _deduplicate_detections([generic_overlap, employee, generic_second_overlap])

        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(deduplicated[0].identity, "Demo User")
        self.assertEqual(deduplicated[0].entity_type, "employee")

    def test_deduplicate_detections_keeps_separate_people(self) -> None:
        left_person = Detection(
            label="person",
            entity_type="person",
            confidence=0.82,
            bbox=BoundingBox(x1=20, y1=50, x2=180, y2=430),
            track_id="t1",
        )
        right_person = Detection(
            label="person",
            entity_type="person",
            confidence=0.8,
            bbox=BoundingBox(x1=360, y1=55, x2=600, y2=425),
            track_id="t2",
        )

        deduplicated = _deduplicate_detections([left_person, right_person])

        self.assertEqual(len(deduplicated), 2)
        self.assertCountEqual([d.track_id for d in deduplicated], ["t1", "t2"])

    def test_assign_presence_sessions_reuses_employee_presence_with_new_track(self) -> None:
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
                entity_type="employee",
                confidence=0.88,
                bbox=BoundingBox(x1=100, y1=70, x2=300, y2=410),
                track_id="t1",
                identity="Demo User",
                zone_id="zone-1",
                details={"employee_id": "employee-1"},
            )
            second = Detection(
                label="person",
                entity_type="employee",
                confidence=0.9,
                bbox=BoundingBox(x1=108, y1=75, x2=308, y2=415),
                track_id="t2",
                identity="Demo User",
                zone_id="zone-1",
                details={"employee_id": "employee-1"},
            )

            first_annotated = pipeline._assign_presence_sessions([first])[0]
            second_annotated = pipeline._assign_presence_sessions([second])[0]

            self.assertEqual(first_annotated.details["presence_key"], second_annotated.details["presence_key"])
            self.assertTrue(first_annotated.details["presence_is_new"])
            self.assertFalse(second_annotated.details["presence_is_new"])

    def test_stabilize_identities_keeps_employee_identity_on_same_track(self) -> None:
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

            recognized = Detection(
                label="person",
                entity_type="employee",
                confidence=0.9,
                bbox=BoundingBox(x1=100, y1=70, x2=300, y2=410),
                track_id="t1",
                identity="Demo User",
                details={
                    "employee_id": "employee-1",
                    "employee_code": "EMP-001",
                    "role_title": "Staff",
                },
            )
            flickered = Detection(
                label="person",
                entity_type="person",
                confidence=0.88,
                bbox=BoundingBox(x1=103, y1=75, x2=303, y2=415),
                track_id="t1",
                details={},
            )

            first_pass = pipeline._stabilize_identities([recognized])[0]
            second_pass = pipeline._stabilize_identities([flickered])[0]

            self.assertEqual(first_pass.entity_type, "employee")
            self.assertEqual(second_pass.entity_type, "employee")
            self.assertEqual(second_pass.identity, "Demo User")
            self.assertEqual(second_pass.details["employee_id"], "employee-1")

    def test_unknown_restricted_person_waits_before_alert_and_employee_upgrade_wins(self) -> None:
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

            unknown = Detection(
                label="person",
                entity_type="person",
                confidence=0.88,
                bbox=BoundingBox(x1=100, y1=70, x2=300, y2=410),
                track_id="t1",
                zone_id="zone-1",
                details={
                    "track_is_new": True,
                    "presence_key": "p1",
                    "presence_is_new": True,
                    "zone_restricted": True,
                },
            )
            upgraded = Detection(
                label="person",
                entity_type="employee",
                confidence=0.9,
                bbox=BoundingBox(x1=102, y1=72, x2=302, y2=412),
                track_id="t1",
                zone_id="zone-1",
                identity="Demo User",
                details={
                    "track_is_new": False,
                    "presence_key": "p1",
                    "presence_is_new": False,
                    "zone_restricted": True,
                    "employee_id": "employee-1",
                    "employee_code": "EMP-001",
                },
            )

            self.assertFalse(pipeline._should_publish(unknown))
            self.assertTrue(pipeline._should_publish(upgraded))


if __name__ == "__main__":
    unittest.main()
