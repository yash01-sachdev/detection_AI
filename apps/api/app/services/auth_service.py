from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import TokenResponse


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def issue_access_token(user: User) -> TokenResponse:
    return TokenResponse(access_token=create_access_token(user.id))


def bootstrap_default_admin(db: Session) -> None:
    settings = get_settings()
    existing = db.scalar(select(User).where(User.email == settings.bootstrap_admin_email.lower()))
    if existing is not None:
        return

    user = User(
        email=settings.bootstrap_admin_email.lower(),
        full_name=settings.bootstrap_admin_full_name,
        hashed_password=hash_password(settings.bootstrap_admin_password),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
