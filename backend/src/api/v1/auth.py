"""
Authentication API endpoints.

Provides register, login, refresh, profile, and account management
backed by JWT tokens and the users table.
"""
import re

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from uuid import UUID

from jose import JWTError

from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...core.utils.timezone import DEFAULT_TIMEZONE_NAME
from ...core.auth import get_current_user as _get_current_user_id
from ...core.auth.auth_service import (
    authenticate_user,
    register_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from ...modules.member.models.user import User
from ...modules.member.models.member import Member
from sqlalchemy import select

router = APIRouter(prefix="/auth", tags=["Authentication"])


# --------------- Request / Response schemas ---------------


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    nickname: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^\+?[1-9]\d{6,18}$", v):
            raise ValueError("Invalid phone number format")
        return v


class LoginRequest(BaseModel):
    login: Optional[str] = None
    username: Optional[str] = None
    password: str

    @property
    def effective_login(self) -> str:
        """Return login identifier — accepts either 'login' or 'username' field."""
        return self.login or self.username or ""


class RefreshRequest(BaseModel):
    refresh_token: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
    nickname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    family_id: str
    timezone: str


class UpdateProfileRequest(BaseModel):
    username: Optional[str] = None
    nickname: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    timezone: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class DeleteAccountRequest(BaseModel):
    password: str


class MessageResponse(BaseModel):
    message: str


# --------------- Helpers ---------------


async def _load_user(user_id: UUID, db: AsyncSession) -> User:
    """Load User ORM object by ID. Raises 401 if not found/inactive."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )
    return user


async def _get_or_create_self_member(user: User, db: AsyncSession) -> Member:
    """Get the self-Member record (source of truth for profile).

    Self-member is identified by Member.id == User.id (shared UUID).
    If not found, creates one for pre-existing users.
    """
    # member.id == user.id (unified ID)
    result = await db.execute(
        select(Member).where(Member.id == user.id)
    )
    self_member = result.scalar_one_or_none()

    # Create new self-member for pre-existing users
    if self_member is None:
        self_member = Member(
            id=user.id,
            family_id=user.family_id,
            created_by=user.id,
            name=user.username,
            nickname=user.nickname,
            phone=user.phone,
            email=user.email,
            profile_completion=30,
        )
        db.add(self_member)
        await db.flush()
    elif self_member.is_deleted:
        self_member.is_deleted = False
        await db.flush()

    return self_member


# --------------- Endpoints ---------------


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user. Returns JWT token pair."""
    if not request.email and not request.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either email or phone is required",
        )
    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    # Check for existing email/phone
    if request.email:
        existing = await db.execute(
            select(User).where(User.email == request.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    if request.phone:
        existing = await db.execute(
            select(User).where(User.phone == request.phone)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone already registered")

    user = await register_user(
        db,
        username=request.username,
        password=request.password,
        email=request.email,
        phone=request.phone,
        nickname=request.nickname,
    )

    return LoginResponse(
        access_token=create_access_token(user.id, user.family_id),
        refresh_token=create_refresh_token(user.id, user.family_id),
    )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email/phone and password. Returns JWT token pair."""
    login_id = request.effective_login
    if not login_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'login' or 'username' field is required",
        )
    user = await authenticate_user(db, login_id, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Update last_login_at
    from ...core.utils.timezone import utc_now
    user.last_login_at = utc_now()
    await db.commit()

    return LoginResponse(
        access_token=create_access_token(user.id, user.family_id),
        refresh_token=create_refresh_token(user.id, user.family_id),
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a refresh token for a new token pair."""
    try:
        payload = decode_token(request.refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = UUID(payload["sub"])
    family_id = UUID(payload["family_id"])

    # Verify user still exists and active
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    return LoginResponse(
        access_token=create_access_token(user_id, family_id),
        refresh_token=create_refresh_token(user_id, family_id),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout():
    """Logout (stateless — client discards tokens)."""
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(_get_current_user_id),
):
    """Get current user profile from JWT.

    Profile fields come from the self-Member record (single source of truth).
    Timezone comes from the User record (auth-level setting).
    """
    user = await _load_user(user_id, db)
    self_member = await _get_or_create_self_member(user, db)

    return UserResponse(
        id=str(user.id),
        username=self_member.name,
        nickname=self_member.nickname,
        email=self_member.email,
        phone=self_member.phone,
        family_id=str(user.family_id),
        timezone=user.timezone,
    )


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    request: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(_get_current_user_id),
):
    """Update user profile fields.

    Convention: null = don't change, empty string = clear the field.

    The self-Member record is the single source of truth for profile data.
    Auth-essential fields (username, phone, email) are synced to the User table.
    Timezone is written directly to the User table (auth-level setting).
    """
    user = await _load_user(user_id, db)
    self_member = await _get_or_create_self_member(user, db)

    # --- Write profile fields to Member (source of truth) ---
    if request.username is not None:
        if not request.username.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="用户名不能为空",
            )
        self_member.name = request.username
    if request.nickname is not None:
        self_member.nickname = request.nickname or None
    if request.phone is not None:
        self_member.phone = request.phone or None
    if request.email is not None:
        self_member.email = request.email or None

    # Validate: at least one contact method must remain
    if self_member.phone is None and self_member.email is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="手机号和邮箱至少需要保留一个",
        )

    # --- Sync auth-essential fields from Member → User ---
    user.username = self_member.name
    user.nickname = self_member.nickname
    user.phone = self_member.phone
    user.email = self_member.email

    # Timezone is a User-level setting (not on Member)
    if request.timezone is not None:
        user.timezone = request.timezone or DEFAULT_TIMEZONE_NAME

    await db.commit()
    await db.refresh(self_member)

    return UserResponse(
        id=str(user.id),
        username=self_member.name,
        nickname=self_member.nickname,
        email=self_member.email,
        phone=self_member.phone,
        family_id=str(user.family_id),
        timezone=user.timezone,
    )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(_get_current_user_id),
):
    """Change password (verify old, set new)."""
    user = await _load_user(user_id, db)

    if not verify_password(request.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")

    if len(request.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be at least 6 characters")

    user.password_hash = hash_password(request.new_password)
    await db.commit()

    return MessageResponse(message="Password changed successfully")


@router.delete("/account", response_model=MessageResponse)
async def delete_account(
    request: DeleteAccountRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(_get_current_user_id),
):
    """Soft-delete account (set is_active=False)."""
    user = await _load_user(user_id, db)

    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect")

    user.is_active = False
    await db.commit()

    return MessageResponse(message="Account deactivated")
