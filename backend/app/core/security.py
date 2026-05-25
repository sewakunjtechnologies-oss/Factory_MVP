from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing_extensions import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.services.exceptions import DomainError


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: UUID) -> str:
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        subject = payload.get("sub")
        user_id = UUID(subject) if subject else None
    except (JWTError, ValueError):
        user_id = None

    if user_id is None:
        raise DomainError(status_code=401, detail="Invalid authentication token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise DomainError(status_code=401, detail="Inactive or missing user")
    return user


def require_roles(*roles: UserRole):
    """Build a dependency that admits the given roles plus owner.

    With the role model collapsed to {owner, manager}, this is effectively:
    `owner is always allowed; manager is allowed if listed`.
    """
    allowed = set(roles)

    async def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role == UserRole.owner or user.role in allowed:
            return user
        raise DomainError(status_code=403, detail="You are not authorized to access this feature")

    return dependency


# Canonical gates.
require_owner = require_roles()  # owner-only (manager not in allowed set)
require_owner_or_manager = require_roles(UserRole.manager)

# Back-compat aliases: every legacy per-stage gate now resolves to owner-or-manager,
# matching the consolidated role model. Names are preserved so existing route files
# (`require_allocator`, `require_fabric_verifier`, etc.) continue to import unchanged.
require_manager = require_owner_or_manager
require_allocator = require_owner_or_manager
require_verifier = require_owner_or_manager
require_dispatcher = require_owner_or_manager
require_receipt_reader = require_owner_or_manager
require_fabric_verifier = require_owner_or_manager
require_fabric_allocator = require_owner_or_manager
require_cutting_verifier = require_owner_or_manager
require_stitching_allocator = require_owner_or_manager
require_stitching_verifier = require_owner_or_manager
require_packing_allocator = require_owner_or_manager
require_any_allocator = require_owner_or_manager
require_packer = require_owner_or_manager
require_dispatch_document_user = require_owner_or_manager
require_mill_followup_user = require_owner_or_manager
