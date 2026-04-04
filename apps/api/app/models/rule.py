from sqlalchemy import Boolean, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDMixin
from app.models.enums import RuleSeverity, SiteType


class Rule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "rules"

    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=True, index=True)
    applies_to_site_type: Mapped[SiteType | None] = mapped_column(Enum(SiteType), nullable=True)
    template_key: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    conditions: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    actions: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    severity: Mapped[RuleSeverity] = mapped_column(Enum(RuleSeverity), default=RuleSeverity.medium)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    site = relationship("Site", back_populates="rules")
    alerts = relationship("Alert", back_populates="rule")

