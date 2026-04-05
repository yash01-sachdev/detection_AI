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
        with self.SessionLocal() as db:
            bootstrap_default_admin(db)
            site = create_site_with_default_rules(
                db,
                SiteCreate(
                    name="Office HQ",
                    site_type=SiteType.office,
                    timezone="Asia/Calcutta",
                    description="Main office",
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
                name="Server Room",
                zone_type=ZoneType.restricted,
                color="#ff8800",
                is_restricted=True,
                points=[
                    {"x": 0.0, "y": 0.0},
                    {"x": 640.0, "y": 0.0},
                    {"x": 640.0, "y": 480.0},
                    {"x": 0.0, "y": 480.0},
                ],
            )
            db.add(zone)
            db.commit()

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


if __name__ == "__main__":
    unittest.main()
