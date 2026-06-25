#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User


async def main() -> int:
    email = (os.environ.get("OWNER_EMAIL") or input("Owner email: ")).strip().lower()
    full_name = (os.environ.get("OWNER_NAME") or "Factory Owner").strip()
    password = os.environ.get("OWNER_PASSWORD")
    if not password:
        password = getpass.getpass("Owner password: ")
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 1

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                full_name=full_name,
                email=email,
                password_hash=hash_password(password),
                role=UserRole.owner,
                is_active=True,
            )
            db.add(user)
            action = "created"
        else:
            user.full_name = full_name
            user.password_hash = hash_password(password)
            user.role = UserRole.owner
            user.is_active = True
            action = "updated"
        await db.commit()
    print(f"Owner test account {action}: {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
