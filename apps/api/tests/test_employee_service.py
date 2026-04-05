import tempfile
import unittest
from base64 import b64decode
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import Employee, EmployeeFaceProfile, Site
from app.models.enums import SiteType
from app.schemas.monitoring import EmployeeCreate
from app.services import employee_service


class EmployeeServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self.db = self.SessionLocal()
        self.site = Site(
            name="Office HQ",
            site_type=SiteType.office,
            timezone="Asia/Calcutta",
            description="Employee service tests",
        )
        self.db.add(self.site)
        self.db.commit()
        self.db.refresh(self.site)

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    async def test_create_employee_and_add_face_profile(self) -> None:
        employee = employee_service.create_employee(
            self.db,
            EmployeeCreate(
                site_id=self.site.id,
                employee_code="EMP-100",
                first_name="Smoke",
                last_name="Tester",
                role_title="Engineer",
                is_active=True,
            ),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            original_faces_dir = employee_service.faces_dir
            employee_service.faces_dir = Path(temp_dir)
            try:
                upload = UploadFile(
                    filename="face.png",
                    file=BytesIO(
                        b64decode(
                            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO6p6S0AAAAASUVORK5CYII="
                        )
                    ),
                )
                profile = await employee_service.add_employee_face_profile(self.db, employee.id, upload)
            finally:
                employee_service.faces_dir = original_faces_dir

        stored_employee = self.db.scalar(select(Employee).where(Employee.id == employee.id))
        stored_profile = self.db.scalar(select(EmployeeFaceProfile).where(EmployeeFaceProfile.id == profile.id))

        self.assertIsNotNone(stored_employee)
        self.assertIsNotNone(stored_profile)
        self.assertEqual(stored_employee.employee_code, "EMP-100")
        self.assertEqual(stored_profile.employee_id, employee.id)
        self.assertTrue(stored_profile.source_image_path.startswith("/media/faces/"))

    def test_create_employee_rejects_duplicate_employee_code(self) -> None:
        employee_service.create_employee(
            self.db,
            EmployeeCreate(
                site_id=self.site.id,
                employee_code="EMP-200",
                first_name="First",
                last_name="Person",
                role_title="Engineer",
                is_active=True,
            ),
        )

        with self.assertRaises(HTTPException) as context:
            employee_service.create_employee(
                self.db,
                EmployeeCreate(
                    site_id=self.site.id,
                    employee_code="EMP-200",
                    first_name="Second",
                    last_name="Person",
                    role_title="Engineer",
                    is_active=True,
                ),
            )

        self.assertEqual(context.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
