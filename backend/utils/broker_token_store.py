"""Async helpers for managing encrypted broker tokens in the database."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.orm import BrokerToken
from backend.utils.encryption import decrypt_token, encrypt_token


async def store_broker_tokens(
    db: AsyncSession,
    user_id: UUID,
    broker_id: str,
    access_token: str,
    refresh_token: str | None = None,
    expires_at: datetime | None = None,
) -> None:
    """Encrypt and upsert broker tokens into the broker_tokens table.

    If a row already exists for (user_id, broker_id), it is updated in place.
    Otherwise a new row is inserted.
    """
    # Encrypt the access token
    access_ct, iv, tag = encrypt_token(access_token)

    # Encrypt the refresh token if provided.
    # Stored as "iv:tag:ciphertext" so it can be decrypted independently
    # of the access token's IV/tag (which are stored in separate columns).
    refresh_ct: str | None = None
    if refresh_token is not None:
        r_ct, r_iv, r_tag = encrypt_token(refresh_token)
        refresh_ct = f"{r_iv}:{r_tag}:{r_ct}"

    # Check if a row already exists
    result = await db.execute(
        select(BrokerToken).where(
            BrokerToken.user_id == user_id,
            BrokerToken.broker_id == broker_id,
        )
    )
    existing = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if existing is not None:
        existing.access_token = access_ct
        existing.refresh_token = refresh_ct
        existing.token_iv = iv
        existing.token_tag = tag
        existing.expires_at = expires_at
        existing.last_refreshed = now
        existing.status = "connected"
    else:
        token_row = BrokerToken(
            id=uuid4(),
            user_id=user_id,
            broker_id=broker_id,
            access_token=access_ct,
            refresh_token=refresh_ct,
            token_iv=iv,
            token_tag=tag,
            expires_at=expires_at,
            connected_at=now,
            status="connected",
        )
        db.add(token_row)

    await db.commit()


async def get_broker_tokens(
    db: AsyncSession,
    user_id: UUID,
    broker_id: str,
) -> tuple[str, str | None] | None:
    """Read and decrypt broker tokens from the database.

    Returns (access_token, refresh_token) or None if no tokens are stored.
    """
    result = await db.execute(
        select(BrokerToken).where(
            BrokerToken.user_id == user_id,
            BrokerToken.broker_id == broker_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None

    # Decrypt access token
    access_token = decrypt_token(row.access_token, row.token_iv, row.token_tag)

    # Decrypt refresh token if present
    refresh_token: str | None = None
    if row.refresh_token is not None:
        # Refresh token is stored as "iv:tag:ciphertext"
        parts = row.refresh_token.split(":", 2)
        if len(parts) == 3:
            r_iv, r_tag, r_ct = parts
            refresh_token = decrypt_token(r_ct, r_iv, r_tag)
        else:
            # Fallback: try decrypting with the row-level IV/tag
            refresh_token = decrypt_token(row.refresh_token, row.token_iv, row.token_tag)

    return access_token, refresh_token


async def delete_broker_tokens(
    db: AsyncSession,
    user_id: UUID,
    broker_id: str,
) -> None:
    """Delete the broker token row for the given user and broker."""
    result = await db.execute(
        select(BrokerToken).where(
            BrokerToken.user_id == user_id,
            BrokerToken.broker_id == broker_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is not None:
        await db.delete(row)
        await db.commit()


async def update_broker_status(
    db: AsyncSession,
    user_id: UUID,
    broker_id: str,
    status: str,
) -> None:
    """Update the status field of a broker token row."""
    result = await db.execute(
        select(BrokerToken).where(
            BrokerToken.user_id == user_id,
            BrokerToken.broker_id == broker_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is not None:
        row.status = status
        await db.commit()
