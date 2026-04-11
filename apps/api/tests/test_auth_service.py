import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.main import _legacy_fall_rule_cleanup_statement
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import AdminCreateRequest
from app.services.auth_service import bootstrap_default_admin, create_admin_user


class AuthServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_bootstrap_default_admin_requires_env_values(self) -> None:
        with self.SessionLocal() as db:
            with patch(
                "app.services.auth_service.get_settings",
                return_value=SimpleNamespace(
                    bootstrap_admin_email="",
                    bootstrap_admin_password="",
                    bootstrap_admin_full_name="",
                ),
            ):
                bootstrap_default_admin(db)

            users = list(db.scalars(select(User)))
            self.assertEqual([], users)

    def test_create_admin_user_persists_admin_account(self) -> None:
        with self.SessionLocal() as db:
            created = create_admin_user(
                db,
                AdminCreateRequest(
                    email="admin2@example.com",
                    full_name="Admin Two",
                    password="StrongPass123",
                ),
            )

            self.assertEqual("admin2@example.com", created.email)
            self.assertEqual(UserRole.admin, created.role)
            self.assertTrue(created.is_active)

    def test_create_admin_user_rejects_duplicate_email(self) -> None:
        with self.SessionLocal() as db:
            create_admin_user(
                db,
                AdminCreateRequest(
                    email="duplicate@example.com",
                    full_name="First Admin",
                    password="StrongPass123",
                ),
            )

            with self.assertRaises(HTTPException) as error:
                create_admin_user(
                    db,
                    AdminCreateRequest(
                        email="duplicate@example.com",
                        full_name="Second Admin",
                        password="StrongPass456",
                    ),
                )

            self.assertEqual(409, error.exception.status_code)

    def test_legacy_fall_rule_cleanup_casts_conditions_to_text(self) -> None:
        statement_sql = str(_legacy_fall_rule_cleanup_statement())

        self.assertIn("CAST(conditions AS TEXT)", statement_sql)


if __name__ == "__main__":
    unittest.main()
