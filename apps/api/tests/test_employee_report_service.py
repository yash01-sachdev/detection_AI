import unittest
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import Camera, Employee, Site, Zone
from app.models.enums import CameraSourceType, EntityType, SiteType, ZoneType
from app.schemas.monitoring import DetectionIngestRequest
from app.services.employee_report_service import build_employee_report_at
from app.services.monitoring_service import create_site_with_default_rules, ingest_detection_event
from app.schemas.monitoring import SiteCreate


class EmployeeReportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_build_employee_report_aggregates_presence_zones_and_timeline(self) -> None:
        report_timezone = ZoneInfo("Asia/Calcutta")
        reference_time = datetime.now(UTC).replace(second=0, microsecond=0)
        day_one_start = reference_time - timedelta(days=2, hours=2)
        day_one_restricted = day_one_start + timedelta(minutes=10)
        day_one_repeat = day_one_restricted + timedelta(seconds=10)
        day_two_start = reference_time - timedelta(days=1)

        with self.SessionLocal() as db:
            site = create_site_with_default_rules(
                db,
                SiteCreate(
                    name="Reporting Office",
                    site_type=SiteType.office,
                    timezone="Asia/Calcutta",
                    description="Employee reporting test site",
                ),
            )

            camera = Camera(
                site_id=site.id,
                name="Main Corridor Camera",
                source_type=CameraSourceType.webcam,
                source_value="0",
                is_enabled=True,
            )
            db.add(camera)
            db.flush()

            work_zone = Zone(
                site_id=site.id,
                name="Work Bay",
                zone_type=ZoneType.work_area,
                color="#148A72",
                is_restricted=False,
                points=[
                    {"x": 0.0, "y": 0.0},
                    {"x": 640.0, "y": 0.0},
                    {"x": 640.0, "y": 480.0},
                    {"x": 0.0, "y": 480.0},
                ],
            )
            restricted_zone = Zone(
                site_id=site.id,
                name="Server Room",
                zone_type=ZoneType.restricted,
                color="#dc6c55",
                is_restricted=True,
                points=[
                    {"x": 50.0, "y": 50.0},
                    {"x": 590.0, "y": 50.0},
                    {"x": 590.0, "y": 430.0},
                    {"x": 50.0, "y": 430.0},
                ],
            )
            db.add(work_zone)
            db.add(restricted_zone)
            db.flush()

            employee = Employee(
                site_id=site.id,
                employee_code="EMP-777",
                first_name="Live",
                last_name="Verify",
                role_title="Analyst",
                is_active=True,
            )
            db.add(employee)
            db.commit()
            db.refresh(camera)
            db.refresh(work_zone)
            db.refresh(restricted_zone)
            db.refresh(employee)

            ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=work_zone.id,
                    entity_type=EntityType.employee,
                    label="Live Verify",
                    track_id="t-work-1",
                    confidence=0.91,
                    occurred_at=day_one_start,
                    details={"employee_id": employee.id, "employee_code": employee.employee_code, "source": "unit-test"},
                ),
            )
            first_alert = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=restricted_zone.id,
                    entity_type=EntityType.employee,
                    label="Live Verify",
                    track_id="t-restricted-1",
                    confidence=0.94,
                    occurred_at=day_one_restricted,
                    details={"employee_id": employee.id, "employee_code": employee.employee_code, "source": "unit-test"},
                ),
            )
            second_alert = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=restricted_zone.id,
                    entity_type=EntityType.employee,
                    label="Live Verify",
                    track_id="t-restricted-2",
                    confidence=0.96,
                    occurred_at=day_one_repeat,
                    details={"employee_id": employee.id, "employee_code": employee.employee_code, "source": "unit-test"},
                ),
            )
            ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=work_zone.id,
                    entity_type=EntityType.employee,
                    label="Live Verify",
                    track_id="t-work-2",
                    confidence=0.9,
                    occurred_at=day_two_start,
                    details={"employee_id": employee.id, "employee_code": employee.employee_code, "source": "unit-test"},
                ),
            )

            report = build_employee_report_at(
                db,
                employee.id,
                days=7,
                reference_time=reference_time,
            )

        self.assertEqual(first_alert.alert_id, second_alert.alert_id)
        self.assertEqual(report.employee.employee_code, "EMP-777")
        self.assertEqual(report.employee.full_name, "Live Verify")
        self.assertEqual(report.totals.sighting_count, 4)
        self.assertEqual(report.totals.alert_count, 1)
        self.assertEqual(report.totals.violation_count, 1)
        self.assertEqual(report.totals.zone_visit_count, 3)
        self.assertEqual(report.totals.days_observed, 2)
        self.assertEqual(report.totals.presence_minutes, 11)
        self.assertEqual(len(report.daily_summaries), 2)
        self.assertEqual(report.daily_summaries[0].date, day_two_start.astimezone(report_timezone).date().isoformat())
        self.assertEqual(report.daily_summaries[1].date, day_one_start.astimezone(report_timezone).date().isoformat())
        self.assertEqual(report.daily_summaries[1].alert_count, 1)
        self.assertEqual(report.daily_summaries[1].violation_count, 1)
        self.assertEqual(report.zone_visits[0].zone_name, "Work Bay")
        self.assertEqual(report.zone_visits[0].visit_count, 2)
        self.assertEqual(report.zone_visits[1].zone_name, "Server Room")
        self.assertEqual(report.zone_visits[1].visit_count, 1)
        self.assertEqual(report.recent_timeline[0].item_type, "event")
        self.assertEqual(report.recent_timeline[0].zone_name, "Work Bay")
        self.assertTrue(any(item.item_type == "alert" for item in report.recent_timeline))


if __name__ == "__main__":
    unittest.main()
