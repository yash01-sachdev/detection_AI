import unittest
from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import Alert, Camera, Rule, Zone
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
        self.assertEqual(len(rules), 2)
        self.assertEqual({rule.template_key for rule in rules}, {"office_restricted_zone", "office_desk_inactivity"})

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


if __name__ == "__main__":
    unittest.main()
