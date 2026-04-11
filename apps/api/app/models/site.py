from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDMixin
from app.models.enums import SiteType


class Site(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sites"

    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    site_type: Mapped[SiteType] = mapped_column(Enum(SiteType), index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Calcutta")
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    cameras = relationship("Camera", back_populates="site")
    zones = relationship("Zone", back_populates="site")
    rules = relationship("Rule", back_populates="site")
    alerts = relationship("Alert", back_populates="site")
    events = relationship("Event", back_populates="site")
    known_people = relationship("KnownPerson", back_populates="site")
    worker_assignments = relationship("WorkerAssignment", back_populates="site")
