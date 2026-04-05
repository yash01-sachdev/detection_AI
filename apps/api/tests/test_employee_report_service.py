import unittest
from datetime import UTC, datetime, timedelta

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
        reference_time = datetime(2026, 4, 8, 12, 0, tzinfo=UTC)
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
        self.assertEqual(report.attendance_totals.scheduled_days, 6)
        self.assertEqual(report.attendance_totals.attended_days, 2)
        self.assertEqual(report.attendance_totals.on_time_days, 0)
        self.assertEqual(report.attendance_totals.late_days, 2)
        self.assertEqual(report.attendance_totals.missed_days, 4)
        self.assertEqual(len(report.daily_summaries), 2)
        day_dates = [day.date for day in report.daily_summaries]
        self.assertEqual(day_dates, sorted(day_dates, reverse=True))
        self.assertEqual(len(set(day_dates)), 2)
        restricted_day = next(day for day in report.daily_summaries if day.violation_count == 1)
        self.assertEqual(restricted_day.alert_count, 1)
        self.assertEqual(restricted_day.violation_count, 1)
        self.assertEqual(sum(1 for day in report.attendance_days if day.status == "late"), 2)
        self.assertEqual(report.zone_visits[0].zone_name, "Work Bay")
        self.assertEqual(report.zone_visits[0].visit_count, 2)
        self.assertEqual(report.zone_visits[1].zone_name, "Server Room")
        self.assertEqual(report.zone_visits[1].visit_count, 1)
        self.assertEqual(report.recent_timeline[0].item_type, "event")
        self.assertEqual(report.recent_timeline[0].zone_name, "Work Bay")
        self.assertTrue(any(item.item_type == "alert" for item in report.recent_timeline))

    def test_build_employee_report_surfaces_inactivity_metrics(self) -> None:
        reference_time = datetime(2026, 4, 8, 12, 0, tzinfo=UTC)
        inactive_time = reference_time - timedelta(hours=1)

        with self.SessionLocal() as db:
            site = create_site_with_default_rules(
                db,
                SiteCreate(
                    name="Inactivity Office",
                    site_type=SiteType.office,
                    timezone="Asia/Calcutta",
                    description="Inactivity reporting test site",
                ),
            )

            camera = Camera(
                site_id=site.id,
                name="Desk Camera",
                source_type=CameraSourceType.webcam,
                source_value="0",
                is_enabled=True,
            )
            db.add(camera)
            db.flush()

            desk_zone = Zone(
                site_id=site.id,
                name="Desk Cluster",
                zone_type=ZoneType.desk,
                color="#148A72",
                is_restricted=False,
                points=[
                    {"x": 0.0, "y": 0.0},
                    {"x": 640.0, "y": 0.0},
                    {"x": 640.0, "y": 480.0},
                    {"x": 0.0, "y": 480.0},
                ],
            )
            db.add(desk_zone)
            db.flush()

            employee = Employee(
                site_id=site.id,
                employee_code="EMP-888",
                first_name="Calm",
                last_name="Worker",
                role_title="Operator",
                is_active=True,
            )
            db.add(employee)
            db.commit()
            db.refresh(camera)
            db.refresh(desk_zone)
            db.refresh(employee)

            response = ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=desk_zone.id,
                    entity_type=EntityType.employee,
                    label="Calm Worker",
                    track_id="t-desk-inactive",
                    confidence=0.93,
                    occurred_at=inactive_time,
                    details={
                        "employee_id": employee.id,
                        "employee_code": employee.employee_code,
                        "posture": "inactive",
                        "inactive_seconds": 45,
                        "source": "unit-test",
                    },
                ),
            )
            report = build_employee_report_at(
                db,
                employee.id,
                days=7,
                reference_time=reference_time,
            )

        self.assertIsNone(response.alert_id)
        self.assertEqual(report.totals.inactivity_event_count, 1)
        self.assertEqual(report.totals.longest_inactivity_seconds, 45)
        self.assertEqual(report.daily_summaries[0].inactivity_event_count, 1)
        self.assertEqual(report.recent_timeline[0].title, "EMP-888 marked inactive")
        self.assertEqual(report.recent_timeline[0].inactive_seconds, 45)
        self.assertEqual(report.recent_timeline[0].posture, "inactive")

    def test_build_employee_report_marks_late_and_off_day_activity(self) -> None:
        reference_time = datetime(2026, 4, 6, 18, 0, tzinfo=UTC)
        scheduled_day = datetime(2026, 4, 6, 4, 10, tzinfo=UTC)
        off_day = datetime(2026, 4, 5, 6, 0, tzinfo=UTC)

        with self.SessionLocal() as db:
            site = create_site_with_default_rules(
                db,
                SiteCreate(
                    name="Attendance Office",
                    site_type=SiteType.office,
                    timezone="Asia/Calcutta",
                    description="Shift attendance test site",
                ),
            )

            camera = Camera(
                site_id=site.id,
                name="Attendance Camera",
                source_type=CameraSourceType.webcam,
                source_value="0",
                is_enabled=True,
            )
            db.add(camera)
            db.flush()

            work_zone = Zone(
                site_id=site.id,
                name="Ops Floor",
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
            db.add(work_zone)
            db.flush()

            employee = Employee(
                site_id=site.id,
                employee_code="EMP-990",
                first_name="Shift",
                last_name="Tester",
                role_title="Coordinator",
                is_active=True,
                shift_name="Morning Shift",
                shift_start_time="09:00",
                shift_end_time="17:00",
                shift_grace_minutes=10,
            )
            employee.shift_days = ["mon", "tue", "wed", "thu", "fri"]
            db.add(employee)
            db.commit()
            db.refresh(camera)
            db.refresh(work_zone)
            db.refresh(employee)

            ingest_detection_event(
                db,
                DetectionIngestRequest(
                    site_id=site.id,
                    camera_id=camera.id,
                    zone_id=work_zone.id,
                    entity_type=EntityType.employee,
                    label="Shift Tester",
                    track_id="t-late-1",
                    confidence=0.92,
                    occurred_at=scheduled_day,
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
                    label="Shift Tester",
                    track_id="t-offday-1",
                    confidence=0.9,
                    occurred_at=off_day,
                    details={"employee_id": employee.id, "employee_code": employee.employee_code, "source": "unit-test"},
                ),
            )

            report = build_employee_report_at(
                db,
                employee.id,
                days=7,
                reference_time=reference_time,
            )

        late_day = next(day for day in report.attendance_days if day.status == "late")
        off_day_activity = next(day for day in report.attendance_days if day.status == "off_day_activity")

        self.assertEqual(report.attendance_totals.late_days, 1)
        self.assertEqual(report.attendance_totals.off_day_activity_days, 1)
        self.assertEqual(report.attendance_totals.outside_shift_sighting_count, 1)
        self.assertEqual(late_day.arrival_delta_minutes, 40)
        self.assertFalse(off_day_activity.is_scheduled)


if __name__ == "__main__":
    unittest.main()
