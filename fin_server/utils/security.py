"""Security utilities for password hashing and verification.

This module provides secure password handling using bcrypt.
"""
import bcrypt
import secrets
import hashlib
from typing import Optional

from config import config


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt.

    Args:
        plain: The plaintext password to hash.

    Returns:
        A UTF-8 decoded bcrypt hash string suitable for storage.

    Raises:
        ValueError: If password is not a string or is empty.
    """
    if not isinstance(plain, str):
        raise ValueError("Password must be a string")
    if not plain:
        raise ValueError("Password cannot be empty")

    salt = bcrypt.gensalt(rounds=config.BCRYPT_ROUNDS)
    return bcrypt.hashpw(plain.encode('utf-8'), salt).decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.

    Args:
        plain: The plaintext password to verify.
        hashed: The stored bcrypt hash.

    Returns:
        True if password matches, False otherwise.
    """
    if not plain or not hashed:
        return False

    # Only accept bcrypt hashes
    if not (hashed.startswith('$2b$') or hashed.startswith('$2a$')):
        return False

    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except (ValueError, TypeError):
        return False


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token.

    Args:
        length: Number of bytes (token will be hex encoded, so 2x length chars).

    Returns:
        A hex-encoded secure random string.
    """
    return secrets.token_hex(length)


def hash_token(token: str) -> str:
    """Hash a token for secure storage (e.g., for password reset tokens).

    Uses SHA-256 for fast lookup while maintaining security.

    Args:
        token: The token to hash.

    Returns:
        SHA-256 hex digest of the token.
    """
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks.

    Args:
        a: First string.
        b: Second string.

    Returns:
        True if strings are equal, False otherwise.
    """
    return secrets.compare_digest(a, b)


