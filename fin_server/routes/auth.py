"""Authentication routes for user signup, login, and token management.

This module provides endpoints for:
- User signup (admin and regular users)
- Login with credentials or refresh token
- Token generation and refresh
- User settings and subscriptions
"""
import logging

from flask import Blueprint, request

from config import config
from fin_server.dto.user_dto import UserDTO
from fin_server.repository.mongo_helper import get_collection
from fin_server.security.authentication import AuthSecurity
from fin_server.utils.generator import build_user
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc
from fin_server.utils.validation import validate_signup, validate_signup_user, build_signup_login_response
from fin_server.services.user_service import create_user_and_accounts
from fin_server.services.auth_service import (
    handle_login,
    generate_access_from_refresh,
    generate_new_refresh_token,
    build_token_response,
)
from fin_server.utils.decorators import handle_errors, require_auth

logger = logging.getLogger(__name__)


# Blueprint for auth routes
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Module-level repository
user_repo = get_collection('users')


# =============================================================================
# Signup Endpoints
# =============================================================================

@auth_bp.route('/signup', methods=['POST'])
@handle_errors
def signup():
    """Create the first admin user and company account."""
    logger.info("Signup endpoint called")
    data = request.get_json(force=True)

    # Validate master password if provided
    provided_master = data.get('master_password')
    if provided_master:
        is_valid, error_msg = config.validate_master_password(provided_master)
        if not is_valid:
            logger.warning("Invalid master password for admin signup: %s", error_msg)
            return respond_error(error_msg, status=403 if 'Invalid' in error_msg else 500)

    data.pop('master_password', None)

    # Validate signup data
    is_valid, errors = validate_signup(data)
    if not is_valid:
        logger.warning("Signup validation failed: %s", errors)
        return respond_error(errors, status=400)

    # Ensure admin role and free subscription
    data['roles'] = ['admin']
    subscription = data.get('subscription') or {}
    if 'subscription_type' not in subscription and 'type' not in subscription:
        subscription['subscription_type'] = 'free'
    data['subscription'] = subscription

    # Build and create user
    admin_data = build_user(data)

    created = create_user_and_accounts(user_repo, admin_data, create_user_bank=True, ensure_org_account=True)
    user_id = created.get('user_id')

    logger.info("Admin user created with ID: %s", user_id)
    response = build_signup_login_response(
        success=True,
        message='Admin signup validated and saved.',
        user_id=user_id,
        account_key=admin_data['account_key'],
        user_key=admin_data['user_key']
    )
    return respond_success(response, status=201)


@auth_bp.route('/account/<account_key>/signup', methods=['POST'])
@handle_errors
def signup_user(account_key):
    """Create additional users in an existing account (admin only)."""
    logger.info("Account signup endpoint called for account_key: %s", account_key)

    # Validate admin token
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return respond_error('Missing or invalid admin token', status=401)

    admin_token = auth_header.split(' ', 1)[1]
    if not AuthSecurity.validate_role_token(user_repo, 'users', admin_token, required_role='admin', account_key=account_key):
        logger.warning("Unauthorized admin token or role/account_key")
        return respond_error('Unauthorized: Invalid admin token, role, or account_key', status=401)

    data = request.get_json(force=True)

    # Validate user data
    is_valid, errors = validate_signup_user(data, account_key)
    if not is_valid:
        logger.warning("User signup validation failed: %s", errors)
        return respond_error(errors, status=400)

    # Build and create user
    user_data = build_user(data, account_key)

    created = create_user_and_accounts(user_repo, user_data, create_user_bank=True, ensure_org_account=True)
    user_id = created.get('user_id')

    logger.info("User created with ID: %s", user_id)
    response = build_signup_login_response(
        success=True,
        message='User signup validated and saved.',
        user_id=user_id,
        account_key=account_key,
        user_key=user_data['user_key']
    )
    return respond_success(response, status=201)


# =============================================================================
# Login Endpoints
# =============================================================================

@auth_bp.route('/login', methods=['POST'])
@handle_errors
def login():
    """Login with username/email/phone and password."""
    logger.info("Login endpoint called")
    data = request.get_json(force=True)

    response, status = handle_login(
        username=data.get('username'),
        password=data.get('password'),
        phone=data.get('phone'),
        email=data.get('email')
    )

    if status >= 400:
        return respond_error(response.get('error', 'Login failed'), status=status)
    return respond_success(response, status=status, do_sanitize=False)


@auth_bp.route('/token', methods=['POST'])
@handle_errors
def generate_token():
    """Generate access or refresh tokens."""
    logger.info("Token generation endpoint called")
    data = request.get_json(force=True)

    token_type = data.get('type', 'access_token')
    token = data.get('token') or data.get('refresh_token')
    expires_in = data.get('expires_in')

    # Generate access token from refresh token
    if token_type == 'refresh_token' and token:
        response, status = generate_access_from_refresh(token, expires_in)
        if status >= 400:
            return respond_error(response.get('error', 'Token generation failed'), status=status)
        return respond_success(response, status=status)

    # Generate new refresh token with credentials
    if token_type == 'refresh_token':
        response, status = generate_new_refresh_token(
            username=data.get('username'),
            password=data.get('password'),
            phone=data.get('phone'),
            email=data.get('email'),
            expires_in=expires_in
        )
        if status >= 400:
            return respond_error(response.get('error', 'Token generation failed'), status=status)
        return respond_success(response, status=status, do_sanitize=False)

    # Default: access token flow via login
    response, status = handle_login(
        username=data.get('username'),
        password=data.get('password'),
        phone=data.get('phone'),
        email=data.get('email'),
        refresh_token=data.get('refresh_token'),
        expires_in=expires_in
    )

    if status >= 400:
        return respond_error(response.get('error', 'Token generation failed'), status=status)

    # Return only token for this endpoint
    if response.get('access_token'):
        import time
        expiry = int(time.time()) + int(expires_in) if expires_in else None
        response = build_token_response(access_token=response['access_token'], expires_in=expiry)

    return respond_success(response, status=status, do_sanitize=False)


# =============================================================================
# Logout Endpoint
# =============================================================================

@auth_bp.route('/logout', methods=['POST'])
@handle_errors
@require_auth
def auth_logout(auth_payload):
    """Logout user by clearing refresh tokens."""
    logger.info("/auth/logout called")

    user_key = auth_payload.get('user_key')
    account_key = auth_payload.get('account_key')

    user_dto = UserDTO.find_by_user_key(user_key, account_key)
    if not user_dto:
        return respond_error('User not found', status=404)

    # Check if user has active tokens
    if not user_dto.refresh_tokens:
        return respond_success({'message': 'Already logged out', 'success': True})

    # Clear all refresh tokens
    user_dto._refresh_tokens = []
    user_dto._refresh_token_cache = set()
    user_dto.save()

    return respond_success({'message': 'Logged out successfully', 'success': True})


# =============================================================================
# User Data Endpoints
# =============================================================================

@auth_bp.route('/account/users', methods=['GET'])
@handle_errors
@require_auth
def list_account_users(auth_payload):
    """List users in the current account."""
    logger.info("List account users endpoint called")

    user_key = auth_payload.get('user_key')
    account_key = auth_payload.get('account_key')
    roles = auth_payload.get('roles', [])

    if 'admin' in roles:
        user_list = UserDTO.find_many_by_account(account_key)
        logger.info("Fetched %d users for account", len(user_list))
        return respond_success({'users': user_list})

    # Non-admin sees only self
    user_dto = UserDTO.find_by_user_key(user_key, account_key)
    if not user_dto:
        return respond_error('User not found', status=404)
    return respond_success({'user': user_dto.to_dict()})


@auth_bp.route('/validate', methods=['GET'])
@handle_errors
@require_auth
def validate_token(auth_payload):
    """Validate current access token."""
    logger.info("Validate token endpoint called")

    user_key = auth_payload.get('user_key')
    account_key = auth_payload.get('account_key')

    user_dto = UserDTO.find_by_user_key(user_key, account_key)
    if not user_dto:
        return respond_error('User not found', status=404)

    return respond_success(_build_user_info_response(user_dto))


@auth_bp.route('/me', methods=['GET'])
@handle_errors
@require_auth
def auth_me(auth_payload):
    """Return current authenticated user's info."""
    logger.info("/auth/me endpoint called")

    user_key = auth_payload.get('user_key')
    account_key = auth_payload.get('account_key')

    user_dto = UserDTO.find_by_user_key(user_key, account_key)
    if not user_dto:
        return respond_error('User not found', status=404)

    return respond_success(_build_user_info_response(user_dto))


def _build_user_info_response(user_dto: UserDTO) -> dict:
    """Build user info response for validate/me endpoints."""
    user_dict = user_dto.to_dict()
    user_dict.pop('password', None)
    user_dict.pop('refresh_tokens', None)

    return {
        'user_key': user_dto.user_key,
        'account_key': user_dto.account_key,
        'roles': user_dto.roles,
        'settings': user_dto.settings,
        'subscription': user_dto.subscription,
        'last_active': user_dto.last_active,
        'user': user_dict
    }


# =============================================================================
# Settings Endpoints
# =============================================================================

@auth_bp.route('/settings', methods=['GET', 'PUT'])
@handle_errors
@require_auth
def user_settings(auth_payload):
    """Get or update user settings (deprecated - use /user/settings)."""
    logger.info("/auth/settings called (deprecated)")

    user_key = auth_payload.get('user_key')
    account_key = auth_payload.get('account_key')

    user_dto = UserDTO.find_by_user_key(user_key, account_key)
    if not user_dto:
        return respond_error('User not found', status=404)

    if request.method == 'PUT':
        body = request.get_json(force=True) or {}
        user_dto.settings = body.get('settings') or body
        user_dto.save()

    return respond_success({
        'user_key': user_dto.user_key,
        'account_key': user_dto.account_key,
        'settings': user_dto.settings,
        'subscription': user_dto.subscription
    })


@auth_bp.route('/permissions', methods=['GET'])
@handle_errors
@require_auth
def get_user_permissions(auth_payload):
    """Get user permissions based on roles."""
    logger.info("/auth/permissions called")

    user_key = auth_payload.get('user_key')
    account_key = auth_payload.get('account_key')
    roles = auth_payload.get('roles', [])

    user_dto = UserDTO.find_by_user_key(user_key, account_key)
    if not user_dto:
        return respond_error('User not found', status=404)

    # Get permissions from user document or derive from roles
    permissions = user_dto.to_dict().get('permissions') or user_dto.to_dict().get('actions') or []

    # Build permission response
    return respond_success({
        'user_key': user_key,
        'roles': roles,
        'permissions': permissions,
    })


@auth_bp.route('/subscriptions', methods=['GET', 'PUT'])
@handle_errors
@require_auth
def user_subscriptions(auth_payload):
    """Get or update subscription info."""
    logger.info("Subscriptions endpoint called")

    user_key = auth_payload.get('user_key')
    account_key = auth_payload.get('account_key')
    roles = auth_payload.get('roles', [])

    user_dto = UserDTO.find_by_user_key(user_key, account_key)
    if not user_dto:
        return respond_error('User not found', status=404)

    if request.method == 'PUT':
        if 'admin' not in roles:
            return respond_error('Only admin can update subscriptions', status=403)

        updated_subscription = request.get_json(force=True).get('subscription', {})

        # Update for all users in account
        for user in UserDTO.find_many_by_account(account_key):
            dto = UserDTO.find_by_user_key(user['user_key'], account_key)
            if dto:
                dto.subscription = updated_subscription
                dto.save()

        logger.info("Subscription updated for account: %s", account_key)

    # Build response based on role
    subscription = user_dto.subscription or {}
    if 'admin' in roles:
        resp_subscription = subscription
    else:
        resp_subscription = {
            'subscription_type': subscription.get('subscription_type', ''),
            'expiry': subscription.get('expiry', '')
        }

    return respond_success({
        'user_key': user_key,
        'account_key': account_key,
        'subscription': resp_subscription
    })


@auth_bp.route('/account/<account_key>/company', methods=['GET'])
@handle_errors
@require_auth
def get_company_name(account_key, auth_payload):
    """Get company name for an account."""
    admin_doc = user_repo.find_one({
        'account_key': account_key,
        'roles': {'$in': ['admin']}
    })

    if admin_doc and 'company_name' in admin_doc:
        return respond_success({'company_name': admin_doc['company_name']})
    return respond_error('Company not found', status=404)


# =============================================================================
# API Blueprint for Frontend Compatibility
# =============================================================================

auth_api_bp = Blueprint('auth_api', __name__, url_prefix='/api')


@auth_api_bp.route('/auth/me', methods=['POST'])
@handle_errors
@require_auth
def api_auth_me(auth_payload):
    """API endpoint for /auth/me (POST variant)."""
    user = user_repo.find_one({
        'user_key': auth_payload.get('user_key'),
        'account_key': auth_payload.get('account_key')
    })

    if not user:
        return respond_error('User not found', status=404)

    user_out = normalize_doc(user)
    user_out['_id'] = str(user_out.get('_id'))
    user_out['id'] = user_out.get('user_key') or user_out['_id']

    return respond_success({'user': user_out})


@auth_api_bp.route('/auth/refresh', methods=['POST'])
@handle_errors
def api_auth_refresh():
    """API endpoint for token refresh."""
    data = request.get_json(force=True)
    refresh_token = data.get('refreshToken') or data.get('refresh_token') or data.get('token')

    if not refresh_token:
        return respond_error('Missing refreshToken', status=400)

    payload = AuthSecurity.decode_token(refresh_token)
    user_key = payload.get('user_key')

    user = user_repo.find_one({'user_key': user_key})
    if not user:
        return respond_error('User not found', status=404)

    if not AuthSecurity.validate_refresh_token(user_repo, 'users', user_key, refresh_token):
        return respond_error('Invalid or expired refresh token', status=401)

    access_token = AuthSecurity.encode_token({
        'user_key': user_key,
        'account_key': user.get('account_key'),
        'roles': user.get('roles', []),
        'type': 'access'
    })

    return respond_success({'accessToken': access_token}, status=200, do_sanitize=False)
