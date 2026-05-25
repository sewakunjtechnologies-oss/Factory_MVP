from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest
from app.services.exceptions import DomainError


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, payload: RegisterRequest) -> LoginResponse:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise DomainError(status_code=409, detail="Email is already registered")

    user = User(
        full_name=payload.full_name,
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return LoginResponse(access_token=create_access_token(user.id), user=user)


async def authenticate_user(db: AsyncSession, payload: LoginRequest) -> LoginResponse:
    result = await db.execute(select(User).where(User.email == str(payload.email).lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise DomainError(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise DomainError(status_code=403, detail="User is inactive")
    return LoginResponse(access_token=create_access_token(user.id), user=user)


async def get_or_create_owner(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.role.in_([UserRole.owner, UserRole.admin])).order_by(User.created_at.asc()))
    existing = result.scalars().first()
    if existing is not None:
        return existing
    fallback = User(
        full_name="Owner",
        email="owner@factory.local",
        password_hash=hash_password("owner12345"),
        role=UserRole.owner,
        is_active=True,
    )
    db.add(fallback)
    await db.commit()
    await db.refresh(fallback)
    return fallback
