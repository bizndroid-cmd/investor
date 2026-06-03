"""Request/response schemas for the auth router."""

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    """Request body for user login."""

    email: EmailStr
    password: str
    totp_code: str | None = None


class RefreshRequest(BaseModel):
    """Request body for token refresh."""

    refresh_token: str


class MFAVerifyRequest(BaseModel):
    """Request body for MFA verification."""

    totp_code: str


class MFAVerifyResponse(BaseModel):
    """Response body for MFA verification."""

    verified: bool
