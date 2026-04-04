from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDMixin
from app.models.enums import AlertStatus, RuleSeverity


class Alert(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "alerts"

    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    camera_id: Mapped[str | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True, index=True)
    rule_id: Mapped[str | None] = mapped_column(ForeignKey("rules.id", ondelete="SET NULL"), nullable=True, index=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[RuleSeverity] = mapped_column(Enum(RuleSeverity), default=RuleSeverity.medium)
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus), default=AlertStatus.open)
    snapshot_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    site = relationship("Site", back_populates="alerts")
    camera = relationship("Camera", back_populates="alerts")
    rule = relationship("Rule", back_populates="alerts")
    event = relationship("Event", back_populates="alerts")

