"""Authentication service -- JWT token management and user authentication."""
import uuid
from datetime import timedelta

from ..utils.timezone import utc_now
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.settings import settings
from ...modules.member.models import User


_REFRESH_TOKEN_EXPIRE_DAYS = 30


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: uuid.UUID, family_id: uuid.UUID) -> str:
    expire = utc_now() + timedelta(
        minutes=settings.jwt_expiration_minutes
    )
    payload = {
        "sub": str(user_id),
        "family_id": str(family_id),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID, family_id: uuid.UUID) -> str:
    expire = utc_now() + timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "family_id": str(family_id),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


async def authenticate_user(
    db: AsyncSession, login: str, password: str
) -> Optional[User]:
    """Authenticate by email or phone + password. Returns User or None."""
    result = await db.execute(
        select(User).where(
            User.is_active == True,
            or_(User.email == login, User.phone == login, User.username == login),
        )
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


async def register_user(
    db: AsyncSession,
    *,
    username: str,
    password: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    nickname: Optional[str] = None,
    timezone_str: str = "Asia/Shanghai",
) -> User:
    """Register a new user and create a new family_id for them.

    Also creates a self-Member record (single source of truth for profile data).
    """
    from ...modules.member.models.member import Member

    user_id = uuid.uuid4()
    family_id = uuid.uuid4()

    user = User(
        id=user_id,
        family_id=family_id,
        username=username,
        password_hash=hash_password(password),
        email=email,
        phone=phone,
        nickname=nickname,
        timezone=timezone_str,
    )
    db.add(user)

    # Create self-member: the single source of truth for profile data.
    # Identified by member.id == user.id (no MemberRelation needed).
    self_member = Member(
        id=user_id,
        family_id=family_id,
        created_by=user_id,
        name=username,
        nickname=nickname,
        phone=phone,
        email=email,
        profile_completion=30,
    )
    db.add(self_member)

    await db.commit()
    await db.refresh(user)
    return user
