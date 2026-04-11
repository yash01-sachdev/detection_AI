import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import Camera
from app.models.enums import CameraSourceType, SiteType
from app.schemas.monitoring import SiteCreate, WorkerAssignmentUpdate, WorkerStatusUpdate
from app.services.auth_service import bootstrap_default_admin
from app.services.monitoring_service import create_site_with_default_rules
from app.services.worker_service import build_live_status, save_worker_live_frame, upsert_worker_assignment, record_worker_status


class WorkerServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _create_site_and_camera(self) -> tuple[str, str]:
        with self.SessionLocal() as db:
            bootstrap_default_admin(db)
            site = create_site_with_default_rules(
                db,
                SiteCreate(
                    name="Office HQ",
                    site_type=SiteType.office,
                    timezone="Asia/Calcutta",
                    description="Worker service test site",
                ),
            )
            camera = Camera(
                site_id=site.id,
                name="Desk Cam",
                source_type=CameraSourceType.webcam,
                source_value="1",
                is_enabled=True,
            )
            db.add(camera)
            db.commit()
            db.refresh(site)
            db.refresh(camera)
            return site.id, camera.id

    def test_upsert_assignment_stores_selected_site_and_camera(self) -> None:
        site_id, camera_id = self._create_site_and_camera()

        with self.SessionLocal() as db:
            assignment = upsert_worker_assignment(
                db,
                "detection-ai-worker",
                WorkerAssignmentUpdate(site_id=site_id, camera_id=camera_id, is_active=True),
            )

        self.assertEqual(assignment.worker_name, "detection-ai-worker")
        self.assertEqual(assignment.site_id, site_id)
        self.assertEqual(assignment.camera_id, camera_id)
        self.assertEqual(assignment.camera_source_type, "webcam")
        self.assertEqual(assignment.camera_source, "1")
        self.assertTrue(assignment.is_active)
        self.assertGreaterEqual(assignment.assignment_version, 1)

    def test_live_status_reflects_worker_status_and_uploaded_frame(self) -> None:
        site_id, camera_id = self._create_site_and_camera()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            with patch("app.services.worker_service.live_root", temp_path / "live"):
                with self.SessionLocal() as db:
                    assignment = upsert_worker_assignment(
                        db,
                        "detection-ai-worker",
                        WorkerAssignmentUpdate(site_id=site_id, camera_id=camera_id, is_active=True),
                    )
                    record_worker_status(
                        db,
                        "detection-ai-worker",
                        WorkerStatusUpdate(
                            assignment_version=assignment.assignment_version,
                            camera_connected=True,
                            camera_source_type="webcam",
                            camera_source="1",
                            frame_count=42,
                            last_detection_count=1,
                            last_labels=["demo user (head down) @ desk test zone"],
                            message="Detections found in the current frame.",
                        ),
                    )
                    frame_path = save_worker_live_frame(
                        db,
                        "detection-ai-worker",
                        assignment.assignment_version,
                        b"fake-jpeg-content",
                    )
                    status = build_live_status(db, site_id=site_id)
                    frame_exists = (temp_path / "live" / "detection-ai-worker" / "latest_frame.jpg").exists()

        self.assertEqual(frame_path, "/live-media/detection-ai-worker/latest_frame.jpg")
        self.assertEqual(status.worker_name, "detection-ai-worker")
        self.assertEqual(status.site_id, site_id)
        self.assertEqual(status.camera_id, camera_id)
        self.assertTrue(status.camera_connected)
        self.assertEqual(status.frame_count, 42)
        self.assertEqual(status.last_detection_count, 1)
        self.assertEqual(status.frame_url, "/live-media/detection-ai-worker/latest_frame.jpg")
        self.assertTrue(frame_exists)


if __name__ == "__main__":
    unittest.main()
