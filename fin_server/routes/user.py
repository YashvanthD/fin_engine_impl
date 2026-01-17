"""User routes for profile, settings, and user management.

This module provides endpoints for:
- User profile management
- Settings and notifications
- User listing and CRUD operations

All endpoints are under /api/user/*
"""
import logging

from flask import Blueprint, request

from fin_server.dto.user_dto import UserDTO
from fin_server.repository.mongo_helper import get_collection
from fin_server.services.auth_service import check_password
from fin_server.utils.generator import build_user
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc
from fin_server.utils.security import hash_password
from fin_server.utils.decorators import handle_errors, require_auth, require_admin

logger = logging.getLogger(__name__)

# Single Blueprint for all user routes
user_bp = Blueprint('user', __name__, url_prefix='/api/user')

# Repository
user_repo = get_collection('users')


# =============================================================================
# Helper Functions
# =============================================================================

def _get_display_name(doc):
    """Get display name from user document."""
    if not doc:
        return None
    name = doc.get('name') or doc.get('username')
    if name:
        return name
    parts = [doc.get('first_name'), doc.get('last_name')]
    return ' '.join([p for p in parts if p]) if any(parts) else None


def _get_primary_role(doc):
    """Get primary role from user document."""
    if not doc:
        return None
    roles = doc.get('roles')
    if isinstance(roles, list) and roles:
        return roles[0]
    return doc.get('role')


def _get_user_dto_from_payload(auth_payload):
    """Get user DTO from auth payload. Returns (user_dto, error_response)."""
    user_key = auth_payload.get('user_key')
    account_key = auth_payload.get('account_key')

    user_dto = UserDTO.find_by_user_key(user_key, account_key)
    if not user_dto:
        return None, respond_error('User not found', status=404)

    if not user_dto.refresh_tokens:
        return None, respond_error('User is logged out', status=401)

    return user_dto, None


def _build_user_response(doc):
    """Build frontend-friendly user object from document."""
    if not doc:
        return None

    normalized = normalize_doc(doc) if isinstance(doc, dict) else doc
    uid = normalized.get('user_key') or str(normalized.get('_id'))

    return {
        'id': uid,
        'user_key': uid,
        'email': normalized.get('email'),
        'name': _get_display_name(normalized),
        'role': normalized.get('role'),
        'authorities': normalized.get('authorities', []),
        'phone': normalized.get('phone'),
        'avatar': normalized.get('avatar'),
        'permissions': normalized.get('permissions') or normalized.get('actions') or [],
        'createdAt': normalized.get('created_at') or normalized.get('joinedDate') or normalized.get('joined_date'),
        'lastLogin': normalized.get('last_login') or normalized.get('lastLogin'),
        'managerId': normalized.get('manager_id') or normalized.get('managerId')
    }


# =============================================================================
# Current User Endpoints (/api/user/me, /api/user/profile, etc.)
# =============================================================================

@user_bp.route('/me', methods=['GET'])
@handle_errors
@require_auth
def get_me(auth_payload):
    """Get current user's basic info."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"GET /api/user/me | account_key: {account_key}, user_key: {user_key}")

    user_dto, error = _get_user_dto_from_payload(auth_payload)
    if error:
        return error

    doc = user_dto.to_dict()
    doc.pop('password', None)
    doc.pop('refresh_tokens', None)

    return respond_success({
        'user_key': user_dto.user_key,
        'account_key': user_dto.account_key,
        'role': user_dto.role,
        'authorities': user_dto.authorities,
        'settings': user_dto.settings,
        'subscription': user_dto.subscription,
        'user': doc
    })


@user_bp.route('/profile', methods=['GET'])
@handle_errors
@require_auth
def get_profile(auth_payload):
    """Get current user's profile."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"GET /api/user/profile | account_key: {account_key}, user_key: {user_key}")

    user_dto, error = _get_user_dto_from_payload(auth_payload)
    if error:
        return error

    profile = user_dto.to_dict()
    profile.pop('password', None)
    profile.pop('refresh_tokens', None)

    return respond_success({'user': _build_user_response(profile)})


@user_bp.route('/profile', methods=['PUT'])
@handle_errors
@require_auth
def update_profile(auth_payload):
    """Update user profile fields."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"PUT /api/user/profile | account_key: {account_key}, user_key: {user_key}")

    user_dto, error = _get_user_dto_from_payload(auth_payload)
    if error:
        return error

    data = request.get_json(force=True)
    if not data:
        return respond_error('No data provided', status=400)

    # Allowed profile fields
    allowed_fields = [
        'name', 'first_name', 'firstName' 'last_name', 'lastName', 'dob', 'phone','mobile',
        'address1', 'address2', 'pincode', 'timezone', 'avatar','username', 'bio','status','designation','department','joined_date','joinedDate','password','settings','profile'
    ]
    if data.get('email'):
        allowed_fields.append('email')

    # Extract only allowed fields
    update_data = {k: data[k] for k in allowed_fields if k in data and data[k] is not None}

    if not update_data:
        return respond_error('No valid fields to update', status=400)

    # Handle timezone in settings
    if 'timezone' in update_data:
        user_dto.settings['timezone'] = update_data['timezone']

    # Update profile using the new method
    user_dto.update_fields(update_data)

    # Return updated profile
    profile = user_dto.to_dict()
    profile.pop('password', None)
    profile.pop('refresh_tokens', None)

    return respond_success({
        'message': 'Profile updated',
        'user': _build_user_response(profile)
    })


@user_bp.route('/password', methods=['PUT'])
@handle_errors
@require_auth
def update_password(auth_payload):
    """Change user password."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"PUT /api/user/password | account_key: {account_key}, user_key: {user_key}")

    user_dto, error = _get_user_dto_from_payload(auth_payload)
    if error:
        return error

    data = request.get_json(force=True)

    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not old_password or not new_password:
        return respond_error('Missing password fields', status=400)

    # Verify old password
    stored_pwd = user_dto.to_dict().get('password', '')
    is_valid, _ = check_password(old_password, stored_pwd)

    if not is_valid:
        return respond_error('Old password is incorrect', status=400)

    # Set new password with bcrypt
    user_dto.password = hash_password(new_password)
    user_dto.save()

    return respond_success({'message': 'Password updated'})


@user_bp.route('/logout', methods=['POST'])
@handle_errors
@require_auth
def logout(auth_payload):
    """Logout user by clearing refresh tokens."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"POST /api/user/logout | account_key: {account_key}, user_key: {user_key}")

    user_dto, error = _get_user_dto_from_payload(auth_payload)
    if error:
        return error

    user_dto._refresh_tokens = []
    user_dto._refresh_token_cache = set()
    user_dto.save()

    return respond_success({'message': 'Logged out'})


# =============================================================================
# Settings Endpoints (/api/user/settings/*)
# =============================================================================

@user_bp.route('/settings', methods=['GET'])
@handle_errors
@require_auth
def get_settings(auth_payload):
    """Get user settings and subscription."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"GET /api/user/settings | account_key: {account_key}, user_key: {user_key}")

    user_dto, error = _get_user_dto_from_payload(auth_payload)
    if error:
        return error

    return respond_success({
        'user_key': user_dto.user_key,
        'account_key': user_dto.account_key,
        'settings': user_dto.settings,
        'subscription': user_dto.subscription
    })


@user_bp.route('/settings', methods=['PUT'])
@handle_errors
@require_auth
def update_settings(auth_payload):
    """Update user settings."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"PUT /api/user/settings | account_key: {account_key}, user_key: {user_key}")

    user_dto, error = _get_user_dto_from_payload(auth_payload)
    if error:
        return error

    data = request.get_json(force=True)

    if 'settings' in data:
        user_dto.settings = data['settings']
        user_dto.save()

    return respond_success({'message': 'Settings updated'})


@user_bp.route('/settings/notifications', methods=['PUT'])
@handle_errors
@require_auth
def update_notification_settings(auth_payload):
    """Update notification settings."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"PUT /api/user/settings/notifications | account_key: {account_key}, user_key: {user_key}")

    user_dto, error = _get_user_dto_from_payload(auth_payload)
    if error:
        return error

    data = request.get_json(force=True)

    if 'notifications' in data:
        user_dto.settings['notifications'] = data['notifications']
        user_dto.save()

    return respond_success({'message': 'Notification settings updated'})


@user_bp.route('/settings/help_support', methods=['PUT'])
@handle_errors
@require_auth
def update_help_support(auth_payload):
    """Update help & support settings."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"PUT /api/user/settings/help_support | account_key: {account_key}, user_key: {user_key}")

    user_dto, error = _get_user_dto_from_payload(auth_payload)
    if error:
        return error

    data = request.get_json(force=True)

    if 'help_support' in data:
        user_dto.settings['help_support'] = data['help_support']
        user_dto.save()

    return respond_success({'message': 'Help & support updated'})


# =============================================================================
# User Management CRUD Endpoints (/api/user/list, /api/user/<user_id>)
# =============================================================================

@user_bp.route('/list', methods=['GET'])
@handle_errors
@require_auth
def list_users(auth_payload):
    """List all users in the current account."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"GET /api/user/list | account_key: {account_key}, user_key: {user_key}")

    if not account_key:
        return respond_error('Missing account_key', status=400)

    users = user_repo.find_many({'account_key': account_key})
    show_phone = request.args.get('phone', 'false').lower() == 'true'

    result = []
    for u in users:
        user_obj = _build_user_response(u)
        if not show_phone:
            user_obj.pop('phone', None)
        result.append(user_obj)

    logger.debug(f"Users fetched: {len(result)} users")
    return respond_success({'users': result})


@user_bp.route('/<user_id>', methods=['GET'])
@handle_errors
@require_auth
def get_user(user_id, auth_payload):
    """Get a single user by ID."""
    account_key = auth_payload.get('account_key')
    requester_user_key = auth_payload.get('user_key')
    logger.info(f"GET /api/user/{user_id} | account_key: {account_key}, user_key: {requester_user_key}")

    user = user_repo.find_one({
        'user_key': user_id,
        'account_key': account_key
    }) or user_repo.find_one({'_id': user_id})

    if not user:
        return respond_error('User not found', status=404)

    logger.debug(f"User details fetched for: {user_id}")
    return respond_success({'user': _build_user_response(user)})


@user_bp.route('/', methods=['POST'])
@handle_errors
@require_auth
@require_admin
def create_user(auth_payload):
    """Create a new user (admin only)."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"POST /api/user | account_key: {account_key}, user_key: {user_key}")

    data = request.get_json(force=True)
    user_doc = build_user(data, account_key=account_key)
    inserted_id = user_repo.create(user_doc)

    user_doc['_id'] = inserted_id
    logger.info(f"User created: {user_doc.get('user_key')}")
    return respond_success({'user': _build_user_response(user_doc)}, status=201)


@user_bp.route('/<user_id>', methods=['PUT', 'PATCH'])
@handle_errors
@require_auth
def update_user(user_id, auth_payload):
    """Update a user by ID."""
    account_key = auth_payload.get('account_key')
    requester_user_key = auth_payload.get('user_key')
    logger.info(f"PUT/PATCH /api/user/{user_id} | account_key: {account_key}, user_key: {requester_user_key}")

    data = request.get_json(force=True)

    # Remove sensitive fields that shouldn't be updated directly
    data.pop('password', None)
    data.pop('refresh_tokens', None)

    result = user_repo.update({
        'user_key': user_id,
        'account_key': account_key
    }, data)

    logger.debug(f"User updated: {user_id}")
    return respond_success({'updated': True, 'user_key': user_id})


@user_bp.route('/<user_id>', methods=['DELETE'])
@handle_errors
@require_auth
@require_admin
def delete_user(user_id, auth_payload):
    """Delete a user by ID (admin only)."""
    account_key = auth_payload.get('account_key')
    requester_user_key = auth_payload.get('user_key')
    logger.info(f"DELETE /api/user/{user_id} | account_key: {account_key}, user_key: {requester_user_key}")

    # Prevent self-deletion
    if user_id == requester_user_key:
        return respond_error('Cannot delete yourself', status=400)

    deleted_count = user_repo.delete({
        'user_key': user_id,
        'account_key': account_key
    })

    if deleted_count > 0:
        logger.info(f"User deleted: {user_id}")
        return respond_success({'deleted': True, 'user_key': user_id})
    return respond_error('User not found', status=404)
