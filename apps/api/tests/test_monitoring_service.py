import unittest
from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import Alert, Camera, Event, Rule, Zone
from app.models.enums import CameraSourceType, EntityType, SiteType, ZoneType
from app.schemas.monitoring import DetectionIngestRequest, SiteCreate
from app.services.auth_service import bootstrap_default_admin
from app.services.monitoring_service import create_site_with_default_rules, ingest_detection_event


class MonitoringServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _create_site_camera_zone(
        self,
        *,
        site_type: SiteType,
        zone_type: ZoneType,
        zone_name: str,
        is_restricted: bool,
    ) -> tuple[object, Camera, Zone]:
        with self.SessionLocal() as db:
            bootstrap_default_admin(db)
            site = create_site_with_default_rules(
                db,
                SiteCreate(
                    name=f"{site_type.value.title()} HQ",
                    site_type=site_type,
                    timezone="Asia/Calcutta",
                    description="Monitoring service test site",
                ),
            )

            camera = Camera(
                site_id=site.id,
                name="Front Camera",
                source_type=CameraSourceType.webcam,
                source_value="0",
                is_enabled=True,
            )
            db.add(camera)
            db.flush()

            zone = Zone(
                site_id=site.id,
                name=zone_name,
                zone_type=zone_type,
                color="#ff8800",
                is_restricted=is_restricted,
                points=[
                    {"x": 0.0, "y": 0.0},
                    {"x": 640.0, "y": 0.0},
                    {"x": 640.0, "y": 480.0},
                    {"x": 0.0, "y": 480.0},
                ],
            )
            db.add(zone)
            db.commit()
            db.refresh(camera)
            db.refresh(zone)
            db.refresh(site)
            return site, camera, zone

    def test_create_site_seeds_default_rules(self) -> None:
        with self.SessionLocal() as db:
            site = create_site_with_default_rules(
                db,
                SiteCreate(
                    name="Office HQ",
                    site_type=SiteType.office,
                    timezone="Asia/Calcutta",
                    description="Main office",
                ),
            )

            rules = list(db.scalars(select(Rule).where(Rule.site_id == site.id)))

        self.assertEqual(site.site_type, SiteType.office)
        self.assertEqual(len(rules), 3)
        self.assertEqual(
            {rule.template_key for rule in rules},
            {
                "office_restricted_zone",
                "office_desk_inactivity",
                "office_head_down_watch",
            },
        )

    def test_ingest_restricted_zone_creates_rule_based_alert(self) -> None:
        site, camera, zone = self._create_site_camera_zone(
            site_type=SiteType.office,
            zone_type=ZoneType.restricted,
            zone_name="Server Room",
            is_restricted=True,
        )

        with self.SessionLocal() as db:
            response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=zone.id,
                    entity_type=EntityType.person,
                    label="person",
                    track_id="t1",
                    confidence=0.91,
                    occurred_at=datetime.now(UTC),
                    details={"source": "unit-test"},
                    snapshot_path="/media/snapshots/test.jpg",
                ),
            )

            alert = db.get(Alert, response.alert_id)

        self.assertIsNotNone(response.alert_id)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.title, "Restricted Zone Entry")
        self.assertEqual(alert.details["zone_name"], "Server Room")
        self.assertEqual(alert.details["zone_type"], "restricted")
        self.assertEqual(alert.snapshot_path, "/media/snapshots/test.jpg")

    def test_employee_matches_generic_person_restricted_zone_rule(self) -> None:
        site, camera, zone = self._create_site_camera_zone(
            site_type=SiteType.office,
            zone_type=ZoneType.restricted,
            zone_name="Finance Vault",
            is_restricted=True,
        )

        with self.SessionLocal() as db:
            response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=zone.id,
                    entity_type=EntityType.employee,
                    label="Smoke Tester",
                    track_id="t42",
                    confidence=0.95,
                    occurred_at=datetime.now(UTC),
                    details={"employee_id": "employee-1", "employee_code": "EMP-001", "source": "unit-test"},
                ),
            )
            alert = db.get(Alert, response.alert_id)

        self.assertIsNotNone(response.alert_id)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.title, "Restricted Zone Entry")
        self.assertEqual(alert.details["zone_name"], "Finance Vault")
        self.assertEqual(alert.details["employee_code"], "EMP-001")

    def test_restaurant_smoking_area_alert_requires_employee_match(self) -> None:
        site, camera, zone = self._create_site_camera_zone(
            site_type=SiteType.restaurant,
            zone_type=ZoneType.smoking_area,
            zone_name="Smoking Area",
            is_restricted=True,
        )

        with self.SessionLocal() as db:
            employee_response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=zone.id,
                    entity_type=EntityType.employee,
                    label="Live Verify",
                    track_id="t7",
                    confidence=0.92,
                    occurred_at=datetime.now(UTC),
                    details={"employee_id": "employee-7", "employee_code": "EMP-777", "source": "unit-test"},
                ),
            )
            employee_alert = db.get(Alert, employee_response.alert_id)
            employee_alert_title = employee_alert.title if employee_alert is not None else None

            person_response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=zone.id,
                    entity_type=EntityType.person,
                    label="person",
                    track_id="t8",
                    confidence=0.88,
                    occurred_at=datetime.now(UTC),
                    details={"source": "unit-test"},
                ),
            )

        self.assertIsNotNone(employee_response.alert_id)
        self.assertEqual(employee_alert_title, "Employee In Smoking Area")
        self.assertIsNone(person_response.alert_id)

    def test_office_desk_inactivity_under_threshold_is_suppressed(self) -> None:
        site, camera, zone = self._create_site_camera_zone(
            site_type=SiteType.office,
            zone_type=ZoneType.desk,
            zone_name="Desk Row A",
            is_restricted=False,
        )

        with self.SessionLocal() as db:
            response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=zone.id,
                    entity_type=EntityType.employee,
                    label="Live Verify",
                    track_id="t-desk-1",
                    confidence=0.91,
                    occurred_at=datetime.now(UTC),
                    details={
                        "employee_id": "employee-11",
                        "employee_code": "EMP-011",
                        "posture": "inactive",
                        "inactive_seconds": 28,
                        "source": "unit-test",
                    },
                ),
            )
            event = db.get(Event, response.event_id)
            alerts = list(db.scalars(select(Alert).where(Alert.site_id == site.id)))

        self.assertIsNotNone(event)
        self.assertNotIn("posture", event.details)
        self.assertNotIn("inactive_seconds", event.details)
        self.assertIsNone(response.alert_id)
        self.assertEqual(len(alerts), 0)

    def test_office_desk_inactivity_over_threshold_records_event_without_creating_alert(self) -> None:
        site, camera, zone = self._create_site_camera_zone(
            site_type=SiteType.office,
            zone_type=ZoneType.desk,
            zone_name="Desk Row A",
            is_restricted=False,
        )

        with self.SessionLocal() as db:
            response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=zone.id,
                    entity_type=EntityType.employee,
                    label="Live Verify",
                    track_id="t-desk-2",
                    confidence=0.91,
                    occurred_at=datetime.now(UTC),
                    details={
                        "employee_id": "employee-11",
                        "employee_code": "EMP-011",
                        "posture": "inactive",
                        "inactive_seconds": 620,
                        "source": "unit-test",
                    },
                ),
            )
            event = db.get(Event, response.event_id)
            alerts = list(db.scalars(select(Alert).where(Alert.site_id == site.id)))

        self.assertIsNotNone(event)
        self.assertEqual(event.details["posture"], "inactive")
        self.assertEqual(event.details["inactive_seconds"], 620)
        self.assertIsNone(response.alert_id)
        self.assertEqual(len(alerts), 0)

    def test_office_head_down_desk_creates_alert(self) -> None:
        site, camera, zone = self._create_site_camera_zone(
            site_type=SiteType.office,
            zone_type=ZoneType.desk,
            zone_name="Desk Row B",
            is_restricted=False,
        )

        with self.SessionLocal() as db:
            response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=zone.id,
                    entity_type=EntityType.employee,
                    label="Live Verify",
                    track_id="t-head-down-1",
                    confidence=0.9,
                    occurred_at=datetime.now(UTC),
                    details={
                        "employee_id": "employee-12",
                        "employee_code": "EMP-012",
                        "posture": "head_down",
                        "source": "unit-test",
                    },
                ),
            )
            alert = db.get(Alert, response.alert_id)

        self.assertIsNotNone(alert)
        self.assertEqual(alert.title, "Head-Down Desk Alert")
        self.assertEqual(alert.details["posture"], "head_down")

    def test_plain_person_detection_without_matching_rule_creates_event_but_no_alert(self) -> None:
        site, camera, zone = self._create_site_camera_zone(
            site_type=SiteType.office,
            zone_type=ZoneType.desk,
            zone_name="Desk Test Zone",
            is_restricted=False,
        )

        with self.SessionLocal() as db:
            response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=zone.id,
                    entity_type=EntityType.person,
                    label="person",
                    track_id="t-plain-1",
                    confidence=0.87,
                    occurred_at=datetime.now(UTC),
                    details={"bbox": {"x1": 20, "y1": 20, "x2": 220, "y2": 420}, "source": "unit-test"},
                ),
            )
            event = db.get(Event, response.event_id)
            alerts = list(db.scalars(select(Alert).where(Alert.site_id == site.id)))

        self.assertIsNotNone(event)
        self.assertIsNone(response.alert_id)
        self.assertEqual(len(alerts), 0)

    def test_custom_zone_rule_overrides_generic_default_rule(self) -> None:
        site, camera, zone = self._create_site_camera_zone(
            site_type=SiteType.office,
            zone_type=ZoneType.restricted,
            zone_name="Payroll Room",
            is_restricted=True,
        )

        with self.SessionLocal() as db:
            custom_rule = Rule(
                site_id=site.id,
                applies_to_site_type=SiteType.office,
                template_key="custom_employee_payroll_room",
                name="Employee In Payroll Room",
                description="Alert when a recognized employee enters the payroll room.",
                conditions={"entity_type": "employee", "zone_id": zone.id},
                actions={"create_alert": True, "snapshot": True},
                severity="critical",
                is_default=False,
                is_enabled=True,
            )
            db.add(custom_rule)
            db.commit()

            response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=zone.id,
                    entity_type=EntityType.employee,
                    label="Live Verify",
                    track_id="t-payroll",
                    confidence=0.93,
                    occurred_at=datetime.now(UTC),
                    details={"employee_id": "employee-9", "employee_code": "EMP-909", "source": "unit-test"},
                ),
            )
            alert = db.get(Alert, response.alert_id)

        self.assertIsNotNone(alert)
        self.assertEqual(alert.title, "Employee In Payroll Room")
        self.assertEqual(alert.severity.value, "critical")

    def test_custom_zone_rule_does_not_match_other_zones(self) -> None:
        site, camera, payroll_zone = self._create_site_camera_zone(
            site_type=SiteType.office,
            zone_type=ZoneType.restricted,
            zone_name="Payroll Room",
            is_restricted=True,
        )

        with self.SessionLocal() as db:
            second_zone = Zone(
                site_id=site.id,
                name="Server Room",
                zone_type=ZoneType.restricted,
                color="#c44f4f",
                is_restricted=True,
                points=[
                    {"x": 40.0, "y": 40.0},
                    {"x": 580.0, "y": 40.0},
                    {"x": 580.0, "y": 420.0},
                    {"x": 40.0, "y": 420.0},
                ],
            )
            db.add(second_zone)
            db.add(
                Rule(
                    site_id=site.id,
                    applies_to_site_type=SiteType.office,
                    template_key="custom_employee_payroll_room_only",
                    name="Employee In Payroll Room",
                    description="Alert when a recognized employee enters the payroll room.",
                    conditions={"entity_type": "employee", "zone_id": payroll_zone.id},
                    actions={"create_alert": True, "snapshot": True},
                    severity="critical",
                    is_default=False,
                    is_enabled=True,
                )
            )
            db.commit()
            db.refresh(second_zone)

            response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=second_zone.id,
                    entity_type=EntityType.employee,
                    label="Live Verify",
                    track_id="t-server",
                    confidence=0.91,
                    occurred_at=datetime.now(UTC),
                    details={"employee_id": "employee-9", "employee_code": "EMP-909", "source": "unit-test"},
                ),
            )
            alert = db.get(Alert, response.alert_id)

        self.assertIsNotNone(alert)
        self.assertEqual(alert.title, "Restricted Zone Entry")

    def test_duplicate_employee_alert_updates_existing_alert(self) -> None:
        site, camera, zone = self._create_site_camera_zone(
            site_type=SiteType.office,
            zone_type=ZoneType.restricted,
            zone_name="Finance Vault",
            is_restricted=True,
        )
        first_time = datetime(2026, 4, 5, 10, 0, tzinfo=UTC)
        second_time = datetime(2026, 4, 5, 10, 0, 8, tzinfo=UTC)

        with self.SessionLocal() as db:
            first_response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=zone.id,
                    entity_type=EntityType.employee,
                    label="Live Verify",
                    track_id="t-1",
                    confidence=0.94,
                    occurred_at=first_time,
                    details={"employee_id": "employee-42", "employee_code": "EMP-042", "source": "unit-test"},
                ),
            )
            second_response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=zone.id,
                    entity_type=EntityType.employee,
                    label="Live Verify",
                    track_id="t-2",
                    confidence=0.96,
                    occurred_at=second_time,
                    details={"employee_id": "employee-42", "employee_code": "EMP-042", "source": "unit-test"},
                ),
            )

            alerts = list(db.scalars(select(Alert).where(Alert.site_id == site.id)))
            events = list(db.scalars(select(Event).where(Event.site_id == site.id)))
            alert = db.get(Alert, first_response.alert_id)

        self.assertEqual(first_response.alert_id, second_response.alert_id)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(len(events), 2)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.details["repeat_count"], 2)
        self.assertEqual(alert.details["employee_code"], "EMP-042")
        self.assertEqual(alert.details["first_seen_at"], first_time.isoformat())
        self.assertEqual(alert.details["last_seen_at"], second_time.isoformat())

    def test_different_unknown_tracks_create_separate_alerts(self) -> None:
        site, camera, zone = self._create_site_camera_zone(
            site_type=SiteType.office,
            zone_type=ZoneType.restricted,
            zone_name="Server Room",
            is_restricted=True,
        )
        first_time = datetime(2026, 4, 5, 11, 0, tzinfo=UTC)
        second_time = datetime(2026, 4, 5, 11, 0, 5, tzinfo=UTC)

        with self.SessionLocal() as db:
            first_response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=zone.id,
                    entity_type=EntityType.person,
                    label="person",
                    track_id="t-person-1",
                    confidence=0.91,
                    occurred_at=first_time,
                    details={"source": "unit-test"},
                ),
            )
            second_response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=zone.id,
                    entity_type=EntityType.person,
                    label="person",
                    track_id="t-person-2",
                    confidence=0.89,
                    occurred_at=second_time,
                    details={"source": "unit-test"},
                ),
            )

            alerts = list(db.scalars(select(Alert).where(Alert.site_id == site.id)))

        self.assertNotEqual(first_response.alert_id, second_response.alert_id)
        self.assertEqual(len(alerts), 2)

    def test_nearby_unknown_tracks_merge_when_bbox_stays_in_same_place(self) -> None:
        site, camera, zone = self._create_site_camera_zone(
            site_type=SiteType.office,
            zone_type=ZoneType.general,
            zone_name="Open Floor",
            is_restricted=False,
        )
        first_time = datetime(2026, 4, 9, 3, 40, tzinfo=UTC)
        second_time = datetime(2026, 4, 9, 3, 40, 3, tzinfo=UTC)

        with self.SessionLocal() as db:
            first_response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=zone.id,
                    entity_type=EntityType.person,
                    label="person",
                    track_id="t-person-1",
                    confidence=0.79,
                    occurred_at=first_time,
                    details={
                        "source": "unit-test",
                        "bbox": {"x1": 100, "y1": 50, "x2": 260, "y2": 420},
                    },
                    alert_title="Person detected",
                    alert_description="Test alert",
                ),
            )
            second_response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=zone.id,
                    entity_type=EntityType.person,
                    label="person",
                    track_id="t-person-2",
                    confidence=0.81,
                    occurred_at=second_time,
                    details={
                        "source": "unit-test",
                        "bbox": {"x1": 118, "y1": 52, "x2": 278, "y2": 418},
                    },
                    alert_title="Person detected",
                    alert_description="Test alert",
                ),
            )

            alerts = list(db.scalars(select(Alert).where(Alert.site_id == site.id)))
            merged_alert = db.get(Alert, first_response.alert_id)

        self.assertEqual(first_response.alert_id, second_response.alert_id)
        self.assertEqual(len(alerts), 1)
        self.assertIsNotNone(merged_alert)
        self.assertEqual(merged_alert.details["repeat_count"], 2)


if __name__ == "__main__":
    unittest.main()
