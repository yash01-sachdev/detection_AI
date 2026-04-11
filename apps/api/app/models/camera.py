from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDMixin
from app.models.enums import CameraSourceType


class Camera(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "cameras"

    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[CameraSourceType] = mapped_column(Enum(CameraSourceType))
    source_value: Mapped[str] = mapped_column(String(500))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    site = relationship("Site", back_populates="cameras")
    alerts = relationship("Alert", back_populates="camera")
    events = relationship("Event", back_populates="camera")
    worker_assignments = relationship("WorkerAssignment", back_populates="camera")
