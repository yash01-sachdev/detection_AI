from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDMixin
from app.models.enums import EntityType


class Event(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "events"

    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id", ondelete="SET NULL"), nullable=True, index=True)
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType))
    label: Mapped[str] = mapped_column(String(255))
    track_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    site = relationship("Site", back_populates="events")
    camera = relationship("Camera", back_populates="events")
    zone = relationship("Zone", back_populates="events")
    alerts = relationship("Alert", back_populates="event")

