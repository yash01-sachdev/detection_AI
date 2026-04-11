from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDMixin


class WorkerAssignment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "worker_assignments"

    worker_name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), nullable=True, index=True)
    camera_id: Mapped[str | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    assignment_version: Mapped[int] = mapped_column(Integer, default=1)
    camera_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    reported_camera_source_type: Mapped[str] = mapped_column(String(40), default="")
    reported_camera_source: Mapped[str] = mapped_column(String(500), default="")
    frame_count: Mapped[int] = mapped_column(Integer, default=0)
    last_detection_count: Mapped[int] = mapped_column(Integer, default=0)
    last_labels: Mapped[list[str]] = mapped_column(JSON, default=list)
    message: Mapped[str] = mapped_column(Text, default="")
    frame_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    frame_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=True,
    )

    site = relationship("Site", back_populates="worker_assignments")
    camera = relationship("Camera", back_populates="worker_assignments")
