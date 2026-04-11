from sqlalchemy import Boolean, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDMixin


class KnownPerson(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "known_people"

    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    display_name: Mapped[str] = mapped_column(String(150), index=True)
    notes: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    site = relationship("Site", back_populates="known_people")
    face_profiles = relationship("KnownPersonFaceProfile", back_populates="known_person")


class KnownPersonFaceProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "known_person_face_profiles"

    known_person_id: Mapped[str] = mapped_column(ForeignKey("known_people.id", ondelete="CASCADE"), index=True)
    source_image_path: Mapped[str] = mapped_column(String(500))
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)

    known_person = relationship("KnownPerson", back_populates="face_profiles")
