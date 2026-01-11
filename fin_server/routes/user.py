"""User routes for profile, settings, and user management.

This module provides endpoints for:
- User profile management
- Settings and notifications
- User listing and CRUD operations
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

# Blueprints
user_bp = Blueprint('user', __name__, url_prefix='/user')
user_api_bp = Blueprint('user_api', __name__, url_prefix='/api')

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
        'email': normalized.get('email'),
        'name': _get_display_name(normalized),
        'role': _get_primary_role(normalized),
        'phone': normalized.get('phone'),
        'avatar': normalized.get('avatar'),
        'permissions': normalized.get('permissions') or normalized.get('actions') or [],
        'createdAt': normalized.get('created_at') or normalized.get('joinedDate'),
        'lastLogin': normalized.get('last_login') or normalized.get('lastLogin'),
        'managerId': normalized.get('manager_id') or normalized.get('managerId')
    }


# =============================================================================
# Profile Endpoints
# =============================================================================

@user_bp.route('/profile', methods=['GET'])
@handle_errors
@require_auth
def get_profile(auth_payload):
    """Get current user's profile."""
    logger.debug('GET /user/profile called')

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
    logger.debug('PUT /user/profile called')

    user_dto, error = _get_user_dto_from_payload(auth_payload)
    if error:
        return error

    data = request.get_json(force=True)

    profile_fields = ['first_name', 'last_name', 'dob', 'address1', 'address2', 'pincode', 'timezone']
    profile_data = {k: data[k] for k in profile_fields if k in data}

    if 'timezone' in profile_data:
        user_dto.settings['timezone'] = profile_data['timezone']

    user_dto.save_profile(profile_data)
    return respond_success({'message': 'Profile updated'})


@user_bp.route('/password', methods=['PUT'])
@handle_errors
@require_auth
def update_password(auth_payload):
    """Change user password."""
    logger.debug('PUT /user/password called')

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
    logger.debug('POST /user/logout called')

    user_dto, error = _get_user_dto_from_payload(auth_payload)
    if error:
        return error

    user_dto._refresh_tokens = []
    user_dto._refresh_token_cache = set()
    user_dto.save()

    return respond_success({'message': 'Logged out'})


@user_bp.route('/me', methods=['GET'])
@handle_errors
@require_auth
def get_me(auth_payload):
    """Get current user's basic info."""
    logger.debug('GET /user/me called')

    user_dto, error = _get_user_dto_from_payload(auth_payload)
    if error:
        return error

    doc = user_dto.to_dict()
    doc.pop('password', None)
    doc.pop('refresh_tokens', None)

    return respond_success({
        'user_key': user_dto.user_key,
        'account_key': user_dto.account_key,
        'roles': user_dto.roles,
        'settings': user_dto.settings,
        'subscription': user_dto.subscription,
        'user': doc
    })


# =============================================================================
# Settings Endpoints
# =============================================================================

@user_bp.route('/settings', methods=['GET'])
@handle_errors
@require_auth
def get_settings(auth_payload):
    """Get user settings and subscription."""
    logger.debug('GET /user/settings called')

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
    logger.debug('PUT /user/settings called')

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
    logger.debug('PUT /user/settings/notifications called')

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
    logger.debug('PUT /user/settings/help_support called')

    user_dto, error = _get_user_dto_from_payload(auth_payload)
    if error:
        return error

    data = request.get_json(force=True)

    if 'help_support' in data:
        user_dto.settings['help_support'] = data['help_support']
        user_dto.save()

    return respond_success({'message': 'Help & support updated'})


# =============================================================================
# User Management Endpoints
# =============================================================================

@user_bp.route('/list', methods=['GET'])
@handle_errors
@require_auth
def list_users(auth_payload):
    """List users in the current account."""
    logger.debug('GET /user/list called')

    account_key = auth_payload.get('account_key')

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

    return respond_success({'users': result})


@user_bp.route('/account/<account_key>/user/<user_key>', methods=['DELETE'])
@handle_errors
@require_admin
def delete_user(account_key, user_key, auth_payload):
    """Delete a user (admin only)."""
    logger.debug('DELETE /user/account/%s/user/%s called', account_key, user_key)

    if auth_payload.get('account_key') != account_key:
        return respond_error('Unauthorized', status=403)

    deleted_count = user_repo.delete({'account_key': account_key, 'user_key': user_key})

    if deleted_count > 0:
        return respond_success({'message': 'User deleted'})
    return respond_error('User not found', status=404)


# =============================================================================
# API Blueprint Routes (/api/users)
# =============================================================================

@user_api_bp.route('/users', methods=['GET'])
@handle_errors
@require_auth
def api_list_users(auth_payload):
    """API endpoint to list users."""
    account_key = auth_payload.get('account_key')

    users = user_repo.find({'account_key': account_key})
    result = [_build_user_response(u) for u in users]

    return respond_success({'users': result})


@user_api_bp.route('/users/<user_id>', methods=['GET'])
@handle_errors
@require_auth
def api_get_user(user_id, auth_payload):
    """API endpoint to get a single user."""
    user = user_repo.find_one({
        'user_key': user_id,
        'account_key': auth_payload.get('account_key')
    }) or user_repo.find_one({'_id': user_id})

    if not user:
        return respond_error('User not found', status=404)

    return respond_success({'user': _build_user_response(user)})


@user_api_bp.route('/users', methods=['POST'])
@handle_errors
@require_auth
def api_create_user(auth_payload):
    """API endpoint to create a user."""
    data = request.get_json(force=True)

    user_doc = build_user(data, account_key=auth_payload.get('account_key'))
    inserted_id = user_repo.create(user_doc)

    user_doc['_id'] = inserted_id
    return respond_success({'user': _build_user_response(user_doc)})


@user_api_bp.route('/users/<user_id>', methods=['PATCH'])
@handle_errors
@require_auth
def api_patch_user(user_id, auth_payload):
    """API endpoint to update a user."""
    data = request.get_json(force=True)

    user_repo.update({
        'user_key': user_id,
        'account_key': auth_payload.get('account_key')
    }, data)

    return respond_success({'updated': True})


@user_api_bp.route('/users/<user_id>', methods=['DELETE'])
@handle_errors
@require_auth
def api_delete_user(user_id, auth_payload):
    """API endpoint to delete a user."""
    user_repo.delete({
        'user_key': user_id,
        'account_key': auth_payload.get('account_key')
    })

    return respond_success({'deleted': True})
