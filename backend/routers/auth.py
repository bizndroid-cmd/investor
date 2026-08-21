"""FastAPI auth router with registration, login, logout, refresh, and MFA endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from backend.config import settings
from backend.database import get_db
from backend.models.domain import AuthTokens, MFASetupData, Session
from backend.routers.schemas import (
    LoginRequest,
    MFAVerifyRequest,
    MFAVerifyResponse,
    RefreshRequest,
    RegisterRequest,
)
from backend.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


async def get_redis() -> aioredis.Redis:
    """Dependency that provides a Redis client."""
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client  # type: ignore[misc]
    finally:
        await client.aclose()


def get_auth_service(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> AuthService:
    """Dependency that provides an AuthService instance."""
    return AuthService(db=db, redis=redis)


async def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    auth_service: AuthService = Depends(get_auth_service),
) -> Session:
    """Dependency that extracts and validates the JWT from the Authorization header.

    Returns the current user's session.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'.",
        )
    token = authorization[len("Bearer "):]
    return await auth_service.get_session(token)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """Register a new user."""
    await auth_service.register(email=body.email, password=body.password)
    return {"message": "User registered successfully."}


@router.post("/login", response_model=AuthTokens)
async def login(
    body: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthTokens:
    """Authenticate a user and return tokens."""
    return await auth_service.login(
        email=body.email,
        password=body.password,
        totp_code=body.totp_code,
    )


@router.post("/logout")
async def logout(
    session: Session = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> Response:
    """Invalidate the current session."""
    await auth_service.logout(user_id=session.user_id, session_id=session.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/refresh", response_model=AuthTokens)
async def refresh(
    body: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthTokens:
    """Refresh the access/refresh token pair."""
    return await auth_service.refresh_session(refresh_token=body.refresh_token)


@router.post("/mfa/setup", response_model=MFASetupData)
async def mfa_setup(
    session: Session = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> MFASetupData:
    """Set up MFA for the current user."""
    return await auth_service.setup_mfa(user_id=session.user_id)


@router.post("/mfa/verify", response_model=MFAVerifyResponse)
async def mfa_verify(
    body: MFAVerifyRequest,
    session: Session = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> MFAVerifyResponse:
    """Verify a TOTP code and enable MFA."""
    verified = await auth_service.verify_mfa(
        user_id=session.user_id, totp_code=body.totp_code
    )
    return MFAVerifyResponse(verified=verified)


# ---------------------------------------------------------------------------
# Account management
# ---------------------------------------------------------------------------


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class DeleteAccountRequest(BaseModel):
    password: str  # Must confirm password to delete


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    session: Session = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """Change the current user's password."""
    await auth_service.change_password(
        user_id=session.user_id,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return {"message": "Password changed successfully."}


@router.post("/delete-account")
async def delete_account(
    body: DeleteAccountRequest,
    session: Session = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """Permanently delete the user account and all associated data."""
    await auth_service.delete_account(
        user_id=session.user_id,
        password=body.password,
    )
    return {"message": "Account deleted."}
