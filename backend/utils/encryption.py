"""AES-256-GCM encryption utilities for securing OAuth tokens at rest."""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.config import settings


def _get_key() -> bytes:
    """Derive the 32-byte encryption key from the hex-encoded config value."""
    return bytes.fromhex(settings.token_encryption_key)


def encrypt_token(plaintext: str) -> tuple[str, str, str]:
    """Encrypt a token string using AES-256-GCM.
    Returns (ciphertext_base64, iv_base64, tag_base64).
    """
    key = _get_key()
    iv = os.urandom(12)
    aesgcm = AESGCM(key)

    # AESGCM.encrypt returns ciphertext + 16-byte tag appended
    encrypted = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)

    # Split: everything except last 16 bytes is ciphertext, last 16 bytes is the tag
    ciphertext = encrypted[:-16]
    tag = encrypted[-16:]

    ciphertext_b64 = base64.b64encode(ciphertext).decode("utf-8")
    iv_b64 = base64.b64encode(iv).decode("utf-8")
    tag_b64 = base64.b64encode(tag).decode("utf-8")

    return ciphertext_b64, iv_b64, tag_b64


def decrypt_token(ciphertext: str, iv: str, tag: str) -> str:
    """Decrypt a token encrypted with encrypt_token.
    Args: ciphertext_base64, iv_base64, tag_base64
    Returns: original plaintext string.
    """
    key = _get_key()

    ciphertext_bytes = base64.b64decode(ciphertext)
    iv_bytes = base64.b64decode(iv)
    tag_bytes = base64.b64decode(tag)

    # AESGCM.decrypt expects ciphertext + tag concatenated
    encrypted = ciphertext_bytes + tag_bytes

    aesgcm = AESGCM(key)
    plaintext_bytes = aesgcm.decrypt(iv_bytes, encrypted, None)

    return plaintext_bytes.decode("utf-8")
