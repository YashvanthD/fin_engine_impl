"""Authentication service - centralized auth business logic.

This module provides reusable functions for:
- Password verification (with legacy migration support)
- User loading by various identifiers
- Token payload building
- Response building for auth endpoints
"""
import base64
import datetime
import logging
from typing import Optional, Tuple, Dict, Any

from fin_server.dto.user_dto import UserDTO
from fin_server.repository.mongo_helper import get_collection
from fin_server.security.authentication import AuthSecurity
from fin_server.utils.security import verify_password, hash_password

logger = logging.getLogger(__name__)

# Module-level repository (lazy loaded)
_user_repo = None


def _get_user_repo():
    """Get user repository singleton."""
    global _user_repo
    if _user_repo is None:
        _user_repo = get_collection('users')
    return _user_repo


# =============================================================================
# Password Utilities
# =============================================================================

def encode_password_legacy(pwd: str) -> str:
    """Legacy base64 encoding for passwords (for migration only)."""
    return base64.b64encode(pwd.encode('utf-8')).decode('utf-8')


def check_password(plain: str, stored: str) -> Tuple[bool, Optional[str]]:
    """Check password against stored hash, supporting multiple formats.

    Supported formats:
    1. bcrypt hash (starts with $2b$)
    2. Legacy base64 encoded password

    Returns:
        Tuple of (is_valid, new_bcrypt_hash_if_migration_needed)
        If password matches legacy format, returns new bcrypt hash for migration.
    """
    if not plain or not stored:
        return False, None

    # Check if stored password is bcrypt hash
    if stored.startswith('$2b$') or stored.startswith('$2a$'):
        return verify_password(plain, stored), None

    # Check legacy base64 format
    try:
        if encode_password_legacy(plain) == stored:
            # Password matches, return new bcrypt hash for migration
            new_hash = hash_password(plain)
            return True, new_hash
    except Exception:
        pass

    # Direct comparison as last resort (for dev/test)
    try:
        decoded = base64.b64decode(stored.encode('utf-8')).decode('utf-8')
        if decoded == plain:
            return True, hash_password(plain)
    except Exception:
        pass

    return False, None


# =============================================================================
# User Loading Functions
# =============================================================================

def load_user_by_identifier(
    username: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None
) -> Tuple[Optional[Dict], Optional[UserDTO]]:
    """Load user document and DTO by username, phone, or email.

    Returns:
        Tuple of (user_doc, user_dto) or (None, None) if not found.
    """
    query = {}
    if username:
        query['username'] = username
    if phone:
        query['phone'] = phone
    if email:
        query['email'] = email

    if not query:
        return None, None

    user_repo = _get_user_repo()
    user_doc = user_repo.find_one(query)

    if not user_doc:
        return None, None

    # Try to get from cache first
    user_key = user_doc.get('user_key')
    user_dto = UserDTO.get_from_cache(user_key) if user_key else None

    if not user_dto:
        user_dto = _build_user_dto_from_doc(user_doc)

    return user_doc, user_dto


def load_user_by_user_key(user_key: str, account_key: Optional[str] = None) -> Optional[UserDTO]:
    """Load user DTO by user_key, optionally validating account_key."""
    user_dto = UserDTO.find_by_user_key(user_key, account_key)
    if account_key and user_dto and user_dto.account_key != account_key:
        return None
    return user_dto


def _build_user_dto_from_doc(user_doc: Dict) -> Optional[UserDTO]:
    """Build UserDTO from a user document."""
    if not user_doc:
        return None

    # Normalize keys
    normalized = {}
    for k, v in user_doc.items():
        if k == '_id':
            normalized['user_id'] = v
        elif k.lower() == 'account_key':
            normalized['account_key'] = v
        elif k.lower() == 'user_key':
            normalized['user_key'] = v
        else:
            normalized[k.lower()] = v

    # Ensure required keys exist
    if 'account_key' not in normalized or 'user_key' not in normalized:
        return None

    return UserDTO(**normalized)


# =============================================================================
# Token Payload Builders
# =============================================================================

def build_access_payload(user_dto: UserDTO) -> Dict[str, Any]:
    """Build access token payload from UserDTO."""
    return {
        'user_key': user_dto.user_key,
        'account_key': user_dto.account_key,
        'role': user_dto.role,
        'authorities': user_dto.authorities,
        'type': 'access'
    }


def build_refresh_payload(user_dto: UserDTO) -> Dict[str, Any]:
    """Build refresh token payload from UserDTO."""
    return {
        'user_key': user_dto.user_key,
        'account_key': user_dto.account_key,
        'role': user_dto.role,
        'authorities': user_dto.authorities,
        'type': 'refresh'
    }


# =============================================================================
# Response Builders
# =============================================================================

def build_user_response(
    user_dto: UserDTO,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None
) -> Dict[str, Any]:
    """Build standardized user response for auth endpoints."""
    user_dict = user_dto.to_dict()
    # Remove sensitive fields
    user_dict.pop('password', None)
    user_dict.pop('refresh_tokens', None)

    response = {
        'success': True,
        'user_key': user_dto.user_key,
        'account_key': user_dto.account_key,
        'role': user_dto.role,
        'authorities': user_dto.authorities,
        'settings': user_dto.settings,
        'subscription': user_dto.subscription,
        'user': {k: v for k, v in user_dict.items() if k not in ['password', 'refresh_tokens']}
    }

    if access_token:
        response['access_token'] = access_token
    if refresh_token:
        response['refresh_token'] = refresh_token

    return response


def build_token_response(
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
    expires_in: Optional[int] = None
) -> Dict[str, Any]:
    """Build token-only response."""
    response = {}
    if access_token:
        response['access_token'] = access_token
    if refresh_token:
        response['refresh_token'] = refresh_token
    if expires_in:
        response['expires_in'] = str(expires_in)
    return response


# =============================================================================
# Login/Token Generation
# =============================================================================

def handle_login(
    username: Optional[str] = None,
    password: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    refresh_token: Optional[str] = None,
    expires_in: Optional[int] = None
) -> Tuple[Dict[str, Any], int]:
    """Handle login or token refresh request.

    Args:
        username: Username for login
        password: Password for login
        phone: Phone for login
        email: Email for login
        refresh_token: Existing refresh token for token refresh
        expires_in: Custom expiry in seconds

    Returns:
        Tuple of (response_dict, http_status_code)
    """
    user_repo = _get_user_repo()

    # Case 1: Use refresh token
    if refresh_token:
        return _handle_refresh_token_login(refresh_token, expires_in, user_repo)

    # Case 2: Use credentials
    if (username or phone or email) and password:
        return _handle_credential_login(
            username=username,
            password=password,
            phone=phone,
            email=email,
            expires_in=expires_in,
            user_repo=user_repo
        )

    # Invalid request
    logger.warning("No valid credentials or refresh token provided")
    return {'success': False, 'error': 'Provide either refresh_token or username/phone/email/password'}, 400


def _handle_refresh_token_login(
    refresh_token: str,
    expires_in: Optional[int],
    user_repo
) -> Tuple[Dict[str, Any], int]:
    """Handle login via refresh token."""
    logger.info("Attempting token generation from refresh token")

    payload = AuthSecurity.decode_token(refresh_token)
    user_key = payload.get('user_key')
    account_key = payload.get('account_key')

    user_dto = load_user_by_user_key(user_key, account_key)
    if not user_dto:
        logger.warning("User not found for user_key: %s", user_key)
        return {'success': False, 'error': 'User not found'}, 404

    # Cleanup expired tokens
    AuthSecurity.validate_and_cleanup_refresh_tokens(user_dto, create_new=False)

    # Validate the refresh token
    if not AuthSecurity.validate_refresh_token(user_repo, 'users', user_key, refresh_token):
        logger.warning("Invalid or expired refresh token")
        return {'success': False, 'error': 'Invalid or expired refresh token'}, 401

    # Generate new access token
    expires_delta = datetime.timedelta(seconds=int(expires_in)) if expires_in else None
    access_token = AuthSecurity.encode_token(build_access_payload(user_dto), expires_delta=expires_delta)

    logger.info("Access token generated from refresh token")
    return build_user_response(user_dto, access_token=access_token), 200


def _handle_credential_login(
    username: Optional[str],
    password: str,
    phone: Optional[str],
    email: Optional[str],
    expires_in: Optional[int],
    user_repo
) -> Tuple[Dict[str, Any], int]:
    """Handle login via credentials (username/phone/email + password)."""
    logger.info("Attempting login with credentials")

    user_doc, user_dto = load_user_by_identifier(username=username, phone=phone, email=email)

    if not user_doc or not user_dto:
        logger.warning("Invalid credentials: user not found")
        return {'success': False, 'error': 'Invalid credentials'}, 401

    # Verify password
    stored_pwd = user_doc.get('password', '')
    is_valid, new_hash = check_password(password, stored_pwd)

    if not is_valid:
        logger.warning("Invalid credentials: password mismatch")
        return {'success': False, 'error': 'Invalid credentials'}, 401

    # Update last active
    user_dto.touch()

    # Migrate password to bcrypt if needed
    if new_hash:
        user_dto.password = new_hash

    # Cleanup expired refresh tokens
    AuthSecurity.validate_and_cleanup_refresh_tokens(user_dto, create_new=False)

    # Generate tokens
    expires_delta = datetime.timedelta(seconds=int(expires_in)) if expires_in else None
    access_token = AuthSecurity.encode_token(build_access_payload(user_dto), expires_delta=expires_delta)

    new_refresh_token = AuthSecurity.create_refresh_token(build_refresh_payload(user_dto))
    user_dto.add_refresh_token(new_refresh_token)

    # Persist changes
    user_repo.update({"user_key": user_dto.user_key}, user_dto.to_dict())

    logger.info("Login successful for user: %s", user_dto.user_key)
    return build_user_response(user_dto, access_token=access_token, refresh_token=new_refresh_token), 200


# =============================================================================
# Token Generation (Non-Login)
# =============================================================================

def generate_access_from_refresh(
    refresh_token: str,
    expires_in: Optional[int] = None
) -> Tuple[Dict[str, Any], int]:
    """Generate a new access token from a valid refresh token.

    Returns only the access token, not full user data.
    """
    import time

    user_repo = _get_user_repo()

    payload = AuthSecurity.decode_token(refresh_token)
    user_key = payload.get('user_key')
    account_key = payload.get('account_key')

    user_dto = load_user_by_user_key(user_key, account_key)
    if not user_dto:
        return {'success': False, 'error': 'User not found'}, 404

    if not AuthSecurity.validate_refresh_token(user_repo, 'users', user_key, refresh_token):
        return {'success': False, 'error': 'Invalid or expired refresh token'}, 401

    expires_delta = datetime.timedelta(seconds=int(expires_in)) if expires_in else None
    access_token = AuthSecurity.encode_token(build_access_payload(user_dto), expires_delta=expires_delta)

    expiry = int(time.time()) + int(expires_in) if expires_in else None
    return build_token_response(access_token=access_token, expires_in=expiry), 200


def generate_new_refresh_token(
    username: Optional[str] = None,
    password: str = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    expires_in: Optional[int] = None
) -> Tuple[Dict[str, Any], int]:
    """Generate a new refresh token using credentials."""
    import time

    if not password or not (username or phone or email):
        return {'success': False, 'error': 'Password and user identifier required'}, 400

    user_repo = _get_user_repo()
    user_doc, user_dto = load_user_by_identifier(username=username, phone=phone, email=email)

    if not user_doc or not user_dto:
        return {'success': False, 'error': 'Invalid credentials'}, 401

    stored_pwd = user_doc.get('password', '')
    is_valid, _ = check_password(password, stored_pwd)

    if not is_valid:
        return {'success': False, 'error': 'Invalid credentials'}, 401

    user_dto.touch()

    new_refresh_token = AuthSecurity.create_refresh_token(build_refresh_payload(user_dto))
    user_dto.add_refresh_token(new_refresh_token)
    user_repo.update({"user_key": user_dto.user_key}, user_dto.to_dict())

    expiry = int(time.time()) + int(expires_in) if expires_in else None
    return build_token_response(refresh_token=new_refresh_token, expires_in=expiry), 200

