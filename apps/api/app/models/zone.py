from sqlalchemy import Boolean, Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDMixin
from app.models.enums import ZoneType


class Zone(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "zones"

    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    zone_type: Mapped[ZoneType] = mapped_column(Enum(ZoneType))
    color: Mapped[str] = mapped_column(String(32), default="#148A72")
    is_restricted: Mapped[bool] = mapped_column(Boolean, default=False)
    points: Mapped[list[dict[str, float]]] = mapped_column(JSON, default=list)

    site = relationship("Site", back_populates="zones")
    events = relationship("Event", back_populates="zone")

