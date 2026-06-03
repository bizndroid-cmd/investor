from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from backend.models.domain import AuthTokens, MFASetupData, Session


class IAuthService(ABC):
    """Abstract base class for dashboard-level authentication.

    Manages user registration, login, session lifecycle, and MFA.
    Broker OAuth flows are handled by the individual IBrokerConnector
    implementations, not here.
    """

    @abstractmethod
    async def register(self, email: str, password: str) -> None:
        """Register a new user with the given email and password."""
        ...

    @abstractmethod
    async def login(
        self,
        email: str,
        password: str,
        totp_code: str | None = None,
    ) -> AuthTokens:
        """Authenticate a user and return a JWT access/refresh token pair.

        If MFA is enabled for the account, ``totp_code`` must be provided.
        """
        ...

    @abstractmethod
    async def logout(self, user_id: UUID, session_id: UUID) -> None:
        """Invalidate the specified session for the given user."""
        ...

    @abstractmethod
    async def refresh_session(self, refresh_token: str) -> AuthTokens:
        """Issue a new access/refresh token pair from a valid refresh token."""
        ...

    @abstractmethod
    async def setup_mfa(self, user_id: UUID) -> MFASetupData:
        """Generate a TOTP secret and provisioning URI for MFA enrollment."""
        ...

    @abstractmethod
    async def verify_mfa(self, user_id: UUID, totp_code: str) -> bool:
        """Verify a TOTP code against the user's stored MFA secret."""
        ...

    @abstractmethod
    async def get_session(self, access_token: str) -> Session:
        """Validate an access token and return the associated session."""
        ...
