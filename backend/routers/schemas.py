"""Request/response schemas for the auth router."""

from pydantic import BaseModel, EmailStr, field_validator


# Block disposable/temp email providers
_BLOCKED_DOMAINS = {
    "mailinator.com", "tempmail.com", "guerrillamail.com", "10minutemail.com",
    "throwaway.email", "yopmail.com", "sharklasers.com", "trashmail.com",
    "fakeinbox.com", "dispostable.com", "maildrop.cc", "tempail.com",
}


class RegisterRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def validate_email_domain(cls, v: str) -> str:
        domain = v.split("@")[1].lower()
        if domain in _BLOCKED_DOMAINS:
            raise ValueError("Disposable email addresses are not allowed")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


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
