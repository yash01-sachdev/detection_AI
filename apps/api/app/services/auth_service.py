from sqlalchemy import select
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import AdminCreateRequest, TokenResponse


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def issue_access_token(user: User) -> TokenResponse:
    return TokenResponse(access_token=create_access_token(user.id))


def list_admin_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).where(User.role == UserRole.admin).order_by(User.created_at.desc())))


def create_admin_user(db: Session, payload: AdminCreateRequest) -> User:
    email = payload.email.lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )

    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def bootstrap_default_admin(db: Session) -> None:
    settings = get_settings()
    email = settings.bootstrap_admin_email.strip().lower()
    password = settings.bootstrap_admin_password.strip()
    full_name = settings.bootstrap_admin_full_name.strip()

    if not email or not password or not full_name:
        return

    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        return

    user = User(
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
