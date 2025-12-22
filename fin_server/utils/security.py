import bcrypt


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt.

    Returns a UTF-8 decoded hash string suitable for storage.
    """
    if not isinstance(plain, str):
        raise ValueError("Password must be a string")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode('utf-8'), salt).decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

