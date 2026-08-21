"""Authentication service implementing IAuthService."""

from __future__ import annotations

import base64
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pyotp
import redis.asyncio as aioredis
from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.interfaces.auth_service import IAuthService
from backend.models.domain import AuthTokens, MFASetupData, Session
from backend.models.orm import Session as SessionORM
from backend.models.orm import User

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

# JWT settings
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
SESSION_INACTIVITY_TTL_SECONDS = 30 * 60  # 30 minutes


class AuthService(IAuthService):
    """Concrete implementation of IAuthService."""

    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self._db = db
        self._redis = redis

    async def register(self, email: str, password: str) -> None:
        """Register a new user with the given email and password.
        
        User is created with is_approved=False. Admin must approve via Telegram.
        """
        # Check if email already exists
        result = await self._db.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists.",
            )

        # Hash password and create user (unapproved)
        password_hash = pwd_context.hash(password)
        user = User(id=uuid4(), email=email, password_hash=password_hash, is_approved=False)
        self._db.add(user)
        await self._db.commit()

        # Send Telegram approval request to admin
        try:
            from backend.services.telegram_service import send_approval_request
            await send_approval_request(user_id=str(user.id), email=email)
        except Exception as e:
            logger.warning("Failed to send Telegram approval request: %s", str(e))

    async def login(
        self,
        email: str,
        password: str,
        totp_code: str | None = None,
    ) -> AuthTokens:
        """Authenticate a user and return a JWT access/refresh token pair."""
        # Find user by email
        result = await self._db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None or not pwd_context.verify(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        # Check if account is approved
        if not user.is_approved:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account pending approval. You'll be notified once approved.",
            )

        # Check MFA if enabled
        if user.mfa_enabled:
            if not totp_code:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="MFA code required.",
                )
            if not user.mfa_secret:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="MFA is enabled but no secret is configured.",
                )
            totp = pyotp.TOTP(user.mfa_secret)
            if not totp.verify(totp_code):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid MFA code.",
                )

        # Create session
        session_id = uuid4()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        # Generate tokens
        access_token = self._create_access_token(user.id, session_id)
        refresh_token = self._create_refresh_token(user.id, session_id)

        # Hash refresh token for storage
        refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        # Persist session
        session_orm = SessionORM(
            id=session_id,
            user_id=user.id,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
            last_active=now,
        )
        self._db.add(session_orm)
        await self._db.commit()

        # Set Redis inactivity key
        redis_key = f"session:active:{session_id}"
        await self._redis.set(redis_key, now.isoformat(), ex=SESSION_INACTIVITY_TTL_SECONDS)

        return AuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(self, user_id: UUID, session_id: UUID) -> None:
        """Invalidate the specified session for the given user."""
        # Delete session from DB
        result = await self._db.execute(
            select(SessionORM).where(
                SessionORM.id == session_id,
                SessionORM.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session:
            await self._db.delete(session)
            await self._db.commit()

        # Delete Redis key
        redis_key = f"session:active:{session_id}"
        await self._redis.delete(redis_key)

    async def refresh_session(self, refresh_token: str) -> AuthTokens:
        """Issue a new access/refresh token pair from a valid refresh token."""
        # Decode refresh token
        try:
            payload = jwt.decode(
                refresh_token, settings.secret_key, algorithms=[JWT_ALGORITHM]
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token.",
            )

        user_id = UUID(payload["sub"])
        session_id = UUID(payload["session_id"])
        token_type = payload.get("type")

        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type.",
            )

        # Verify session exists and not expired
        result = await self._db.execute(
            select(SessionORM).where(
                SessionORM.id == session_id,
                SessionORM.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session not found.",
            )

        now = datetime.now(timezone.utc)
        if session.expires_at.replace(tzinfo=timezone.utc) < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired.",
            )

        # Verify refresh token hash matches
        refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        if session.refresh_token_hash != refresh_token_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token.",
            )

        # Issue new token pair
        new_access_token = self._create_access_token(user_id, session_id)
        new_refresh_token = self._create_refresh_token(user_id, session_id)

        # Update session
        new_refresh_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()
        session.refresh_token_hash = new_refresh_hash
        session.last_active = now
        await self._db.commit()

        # Reset Redis inactivity key
        redis_key = f"session:active:{session_id}"
        await self._redis.set(redis_key, now.isoformat(), ex=SESSION_INACTIVITY_TTL_SECONDS)

        return AuthTokens(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def setup_mfa(self, user_id: UUID) -> MFASetupData:
        """Generate a TOTP secret and provisioning URI for MFA enrollment."""
        result = await self._db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        # Generate TOTP secret
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email, issuer_name="StockDashboard"
        )

        # Generate QR code as base64 encoding of the provisioning URI
        qr_code_base64 = base64.b64encode(provisioning_uri.encode("utf-8")).decode(
            "utf-8"
        )

        # Store secret in user record
        user.mfa_secret = secret
        await self._db.commit()

        return MFASetupData(
            secret=secret,
            provisioning_uri=provisioning_uri,
            qr_code_base64=qr_code_base64,
        )

    async def verify_mfa(self, user_id: UUID, totp_code: str) -> bool:
        """Verify a TOTP code against the user's stored MFA secret."""
        result = await self._db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        if not user.mfa_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA not set up for this user.",
            )

        totp = pyotp.TOTP(user.mfa_secret)
        is_valid = totp.verify(totp_code)

        if is_valid:
            user.mfa_enabled = True
            await self._db.commit()

        return is_valid

    async def get_session(self, access_token: str) -> Session:
        """Validate an access token and return the associated session."""
        try:
            payload = jwt.decode(
                access_token, settings.secret_key, algorithms=[JWT_ALGORITHM]
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token.",
            )

        user_id = UUID(payload["sub"])
        session_id = UUID(payload["session_id"])
        token_type = payload.get("type")

        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type.",
            )

        # Check Redis inactivity key
        redis_key = f"session:active:{session_id}"
        exists = await self._redis.exists(redis_key)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired due to inactivity.",
            )

        # Refresh the TTL on activity
        now = datetime.now(timezone.utc)
        await self._redis.set(redis_key, now.isoformat(), ex=SESSION_INACTIVITY_TTL_SECONDS)

        # Fetch session from DB
        result = await self._db.execute(
            select(SessionORM).where(
                SessionORM.id == session_id,
                SessionORM.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session not found.",
            )

        return Session(
            id=session.id,
            user_id=session.user_id,
            expires_at=session.expires_at,
            last_active=session.last_active,
        )

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _create_access_token(self, user_id: UUID, session_id: UUID) -> str:
        """Create a JWT access token (15 min expiry)."""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": str(user_id),
            "session_id": str(session_id),
            "type": "access",
            "exp": expire,
            "iat": now,
        }
        return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)

    def _create_refresh_token(self, user_id: UUID, session_id: UUID) -> str:
        """Create a JWT refresh token (7 days expiry)."""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
            "sub": str(user_id),
            "session_id": str(session_id),
            "type": "refresh",
            "exp": expire,
            "iat": now,
        }
        return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


    async def change_password(self, user_id: UUID, current_password: str, new_password: str) -> None:
        """Change user's password after verifying current password."""
        result = await self._db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        if not pwd_context.verify(current_password, user.password_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect.")

        if len(new_password) < 8:
            raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")

        user.password_hash = pwd_context.hash(new_password)
        await self._db.commit()

    async def delete_account(self, user_id: UUID, password: str) -> None:
        """Permanently delete user and all associated data. Requires password confirmation."""
        result = await self._db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        if not pwd_context.verify(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Password is incorrect.")

        # CASCADE deletes handle all related data (sessions, alerts, holdings, etc.)
        await self._db.delete(user)
        await self._db.commit()
        logger.info("Account deleted for user %s", user_id)
