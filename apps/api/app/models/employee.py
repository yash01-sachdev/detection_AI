from sqlalchemy import Boolean, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDMixin


class Employee(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "employees"

    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    role_title: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    face_profiles = relationship("EmployeeFaceProfile", back_populates="employee")


class EmployeeFaceProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "employee_face_profiles"

    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    source_image_path: Mapped[str] = mapped_column(String(500))
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)

    employee = relationship("Employee", back_populates="face_profiles")

