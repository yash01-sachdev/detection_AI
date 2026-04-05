from collections.abc import Iterable

from sqlalchemy import Boolean, ForeignKey, JSON, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDMixin

DEFAULT_SHIFT_DAYS = "mon,tue,wed,thu,fri"


class Employee(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "employees"

    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    role_title: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    shift_name: Mapped[str] = mapped_column(String(120), default="Day Shift")
    shift_start_time: Mapped[str] = mapped_column(String(5), default="09:00")
    shift_end_time: Mapped[str] = mapped_column(String(5), default="17:00")
    shift_grace_minutes: Mapped[int] = mapped_column(Integer, default=10)
    _shift_days_csv: Mapped[str] = mapped_column("shift_days", String(64), default=DEFAULT_SHIFT_DAYS)

    face_profiles = relationship("EmployeeFaceProfile", back_populates="employee")

    @property
    def shift_days(self) -> list[str]:
        return [part for part in self._shift_days_csv.split(",") if part]

    @shift_days.setter
    def shift_days(self, value: Iterable[str] | str | None) -> None:
        if value is None:
            self._shift_days_csv = DEFAULT_SHIFT_DAYS
            return

        if isinstance(value, str):
            parts = [part.strip().lower() for part in value.split(",")]
        else:
            parts = [str(part).strip().lower() for part in value]

        unique_parts: list[str] = []
        for part in parts:
            if part and part not in unique_parts:
                unique_parts.append(part)

        self._shift_days_csv = ",".join(unique_parts or DEFAULT_SHIFT_DAYS.split(","))


class EmployeeFaceProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "employee_face_profiles"

    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    source_image_path: Mapped[str] = mapped_column(String(500))
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)

    employee = relationship("Employee", back_populates="face_profiles")
