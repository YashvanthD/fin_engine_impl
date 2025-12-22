from flask import Blueprint, request, current_app
from fin_server.dto.user_dto import UserDTO
from fin_server.exception import UnauthorizedError
from fin_server.routes.task import user_repo
from fin_server.security.authentication import get_auth_payload
from fin_server.utils.generator import build_user
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc, get_request_payload
import logging
import base64

# Add debug logging to all endpoints and update route prefixes to /api/v1/
user_bp = Blueprint('user', __name__, url_prefix='/user')
user_api_bp = Blueprint('user_api', __name__, url_prefix='/api')


def _display_name(doc):
    # Return the preferred display name for the user doc
    if not doc:
        return None
    name = doc.get('name') or doc.get('username')
    if name:
        return name
    parts = [doc.get('first_name'), doc.get('last_name')]
    return ' '.join([p for p in parts if p]) if any(parts) else None


def _primary_role(doc):
    if not doc:
        return None
    roles = doc.get('roles')
    if isinstance(roles, list) and roles:
        return roles[0]
    return doc.get('role')


@user_bp.route('/profile', methods=['GET'])
def get_profile():
    current_app.logger.debug('GET /api/v1/user/profile called')
    try:
        payload = get_auth_payload(request)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        user_dto = UserDTO.find_by_user_key(user_key, account_key)
        if not user_dto:
            return respond_error('User not found', status=404)
        # Validate user is not logged out (must have valid refresh tokens)
        if not user_dto.refresh_tokens:
            return respond_error('User is logged out', status=401)
        profile = user_dto.to_dict()
        profile.pop('password', None)
        profile.pop('refresh_tokens', None)
        # Build frontend-friendly User object
        user_out = {
            'id': profile.get('user_key') or profile.get('id') or str(profile.get('_id')),
            'email': profile.get('email'),
            'name': _display_name(profile) or profile.get('name'),
            'role': _primary_role(profile),
            'phone': profile.get('phone'),
            'avatar': profile.get('avatar'),
            'permissions': profile.get('permissions') or profile.get('actions') or [],
            'createdAt': profile.get('created_at') or profile.get('joinedDate'),
            'lastLogin': profile.get('last_login') or profile.get('lastLogin'),
            'managerId': profile.get('manager_id') or profile.get('managerId')
        }
        return respond_success({'user': user_out})
    except ValueError as ve:
        msg = str(ve).lower()
        if 'expired' in msg:
            logging.warning(f"Token expired: {ve}")
            return respond_error('Token expired', status=401)
        if 'invalid token' in msg or 'signature' in msg or 'decode' in msg:
            logging.warning(f"Invalid token: {ve}")
            return respond_error('Invalid token', status=401)
        logging.exception("ValueError in get_profile")
        return respond_error(str(ve), status=401)
    except Exception as e:
        logging.exception("Error in get_profile")
        return respond_error('Server error', status=500)

@user_bp.route('/profile', methods=['PUT'])
def update_profile():
    current_app.logger.debug('PUT /api/v1/user/profile called with data: %s', request.json)
    try:
        payload = get_auth_payload(request)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        user_dto = UserDTO.find_by_user_key(user_key, account_key)
        if not user_dto:
            return respond_error('User not found', status=404)
        # Validate user is not logged out (must have valid refresh tokens)
        if not user_dto.refresh_tokens:
            return respond_error('User is logged out', status=401)
        data = request.get_json(force=True)
        profile_fields = ['first_name', 'last_name', 'dob', 'address1', 'address2', 'pincode', 'timezone']
        profile_data = {k: data[k] for k in profile_fields if k in data}
        # Update timezone in settings if provided
        if 'timezone' in profile_data:
            user_dto.settings['timezone'] = profile_data['timezone']
        user_dto.save_profile(profile_data)
        return respond_success({'message': 'Profile updated'})
    except ValueError as ve:
        msg = str(ve).lower()
        if 'expired' in msg:
            logging.warning(f"Token expired: {ve}")
            return respond_error('Token expired', status=401)
        if 'invalid token' in msg or 'signature' in msg or 'decode' in msg:
            logging.warning(f"Invalid token: {ve}")
            return respond_error('Invalid token', status=401)
        logging.exception("ValueError in update_profile")
        return respond_error(str(ve), status=401)
    except Exception as e:
        logging.exception("Error in update_profile")
        return respond_error('Server error', status=500)

@user_bp.route('/password', methods=['PUT'])
def update_password():
    current_app.logger.debug('PUT /api/v1/user/password called')
    try:
        payload = get_auth_payload(request)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        user_dto = UserDTO.find_by_user_key(user_key, account_key)
        if not user_dto:
            return respond_error('User not found', status=404)
        # Validate user is not logged out (must have valid refresh tokens)
        if not user_dto.refresh_tokens:
            return respond_error('User is logged out', status=401)
        data = request.get_json(force=True)
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        if not old_password or not new_password:
            return respond_error('Missing password fields', status=400)
        db_password = ''
        try:
            if user_dto.password:
                decoded = base64.b64decode(user_dto.password.encode('utf-8'))
                if isinstance(decoded, (bytes, bytearray)):
                    db_password = decoded.decode('utf-8')
                else:
                    db_password = str(decoded)
        except Exception:
            current_app.logger.exception('Failed to decode stored password')
            db_password = ''
        if db_password != old_password:
            return respond_error('Old password incorrect', status=403)
        user_dto.password = base64.b64encode(new_password.encode('utf-8')).decode('utf-8')
        user_dto.save()
        return respond_success({'message': 'Password updated'})
    except ValueError as ve:
        msg = str(ve).lower()
        if 'expired' in msg:
            logging.warning(f"Token expired: {ve}")
            return respond_error('Token expired', status=401)
        if 'invalid token' in msg or 'signature' in msg or 'decode' in msg:
            logging.warning(f"Invalid token: {ve}")
            return respond_error('Invalid token', status=401)
        logging.exception("ValueError in update_password")
        return respond_error(str(ve), status=401)
    except Exception as e:
        logging.exception("Error in update_password")
        return respond_error('Server error', status=500)

@user_bp.route('/logout', methods=['POST'])
def logout():
    current_app.logger.debug('POST /api/v1/user/logout called')
    try:
        payload = get_auth_payload(request)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        user_dto = UserDTO.find_by_user_key(user_key, account_key)
        if not user_dto:
            return respond_error('User not found', status=404)
        user_dto._refresh_tokens = []
        user_dto._refresh_token_cache = set()
        user_dto.save()
        return respond_success({'message': 'Logged out'})
    except ValueError as ve:
        msg = str(ve).lower()
        if 'expired' in msg:
            logging.warning(f"Token expired: {ve}")
            return respond_error('Token expired', status=401)
        if 'invalid token' in msg or 'signature' in msg or 'decode' in msg:
            logging.warning(f"Invalid token: {ve}")
            return respond_error('Invalid token', status=401)
        logging.exception("ValueError in logout")
        return respond_error(str(ve), status=401)
    except Exception as e:
        logging.exception("Error in logout")
        return respond_error('Server error', status=500)

@user_bp.route('/settings', methods=['PUT'])
def update_settings():
    current_app.logger.debug('PUT /api/v1/user/settings called with data: %s', request.json)
    try:
        payload = get_auth_payload(request)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        user_dto = UserDTO.find_by_user_key(user_key, account_key)
        if not user_dto:
            return respond_error('User not found', status=404)
        # Validate user is not logged out (must have valid refresh tokens)
        if not user_dto.refresh_tokens:
            return respond_error('User is logged out', status=401)
        data = request.get_json(force=True)
        if 'settings' in data:
            user_dto.settings = data['settings']
            user_dto.save()
        return respond_success({'message': 'Settings updated'})
    except ValueError as ve:
        msg = str(ve).lower()
        if 'expired' in msg:
            logging.warning(f"Token expired: {ve}")
            return respond_error('Token expired', status=401)
        if 'invalid token' in msg or 'signature' in msg or 'decode' in msg:
            logging.warning(f"Invalid token: {ve}")
            return respond_error('Invalid token', status=401)
        logging.exception("ValueError in update_settings")
        return respond_error(str(ve), status=401)
    except Exception as e:
        logging.exception("Error in update_settings")
        return respond_error('Server error', status=500)

@user_bp.route('/settings/notifications', methods=['PUT'])
def update_notification_settings():
    current_app.logger.debug('PUT /api/v1/user/settings/notifications called with data: %s', request.json)
    try:
        payload = get_auth_payload(request)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        user_dto = UserDTO.find_by_user_key(user_key, account_key)
        if not user_dto:
            return respond_error('User not found', status=404)
        # Validate user is not logged out (must have valid refresh tokens)
        if not user_dto.refresh_tokens:
            return respond_error('User is logged out', status=401)
        data = request.get_json(force=True)
        if 'notifications' in data:
            user_dto.settings['notifications'] = data['notifications']
            user_dto.save()
        return respond_success({'message': 'Notification settings updated'})
    except ValueError as ve:
        msg = str(ve).lower()
        if 'expired' in msg:
            logging.warning(f"Token expired: {ve}")
            return respond_error('Token expired', status=401)
        if 'invalid token' in msg or 'signature' in msg or 'decode' in msg:
            logging.warning(f"Invalid token: {ve}")
            return respond_error('Invalid token', status=401)
        logging.exception("ValueError in update_notification_settings")
        return respond_error(str(ve), status=401)
    except Exception as e:
        logging.exception("Error in update_notification_settings")
        return respond_error('Server error', status=500)

@user_bp.route('/settings/help_support', methods=['PUT'])
def update_help_support():
    current_app.logger.debug('PUT /api/v1/user/settings/help_support called with data: %s', request.json)
    try:
        payload = get_auth_payload(request)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        user_dto = UserDTO.find_by_user_key(user_key, account_key)
        if not user_dto:
            return respond_error('User not found', status=404)
        # Validate user is not logged out (must have valid refresh tokens)
        if not user_dto.refresh_tokens:
            return respond_error('User is logged out', status=401)
        data = request.get_json(force=True)
        if 'help_support' in data:
            user_dto.settings['help_support'] = data['help_support']
            user_dto.save()
        return respond_success({'message': 'Help & support updated'})
    except ValueError as ve:
        msg = str(ve).lower()
        if 'expired' in msg:
            logging.warning(f"Token expired: {ve}")
            return respond_error('Token expired', status=401)
        if 'invalid token' in msg or 'signature' in msg or 'decode' in msg:
            logging.warning(f"Invalid token: {ve}")
            return respond_error('Invalid token', status=401)
        logging.exception("ValueError in update_help_support")
        return respond_error(str(ve), status=401)
    except Exception as e:
        logging.exception("Error in update_help_support")
        return respond_error('Server error', status=500)

@user_bp.route('/list', methods=['GET'])
def list_users():
    current_app.logger.debug('GET /api/v1/user/list called')
    try:
        payload = get_auth_payload(request)
        account_key = payload.get('account_key')
        if not account_key:
            return respond_error('Missing account_key', status=400)
        users = user_repo.find_many({'account_key': account_key})
        show_phone = request.args.get('phone', 'false').lower() == 'true'
        filtered_users = []
        for u in users:
            # normalize DB user doc into frontend User shape
            out = {
                'id': u.get('user_key') or str(u.get('_id')),
                'email': u.get('email'),
                'name': _display_name(u) or u.get('name'),
                'role': _primary_role(u),
                'phone': u.get('phone') if show_phone else None,
                'avatar': u.get('avatar'),
                'permissions': u.get('permissions') or u.get('actions') or [],
                'createdAt': u.get('created_at'),
                'lastLogin': u.get('last_login'),
                'managerId': u.get('manager_id')
            }
            # drop None phone when not requested
            if not show_phone:
                out.pop('phone', None)
            filtered_users.append(out)
        return respond_success({'users': filtered_users})
    except Exception as e:
        logging.exception('Error in list_users')
        return respond_error('Server error', status=500)

@user_bp.route('/account/<account_key>/user/<user_key>', methods=['DELETE'])
def delete_user(account_key, user_key):
    current_app.logger.debug('DELETE /api/v1/user/account/%s/user/%s called', account_key, user_key)
    try:
        payload = get_auth_payload(request)
        roles = payload.get('roles', [])
        if 'admin' not in roles or payload.get('account_key') != account_key:
            return respond_error('Unauthorized', status=403)
        deleted_count = user_repo.delete({'account_key': account_key, 'user_key': user_key})
        if deleted_count > 0:
            return respond_success({'message': 'User deleted'})
        else:
            return respond_error('User not found', status=404)
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception as e:
        logging.exception('Error in delete_user')
        return respond_error('Server error', status=500)

@user_api_bp.route('/users', methods=['GET'])
def api_list_users():
    try:
        payload = get_request_payload()
        account_key = payload.get('account_key')
        users = user_repo.find({'account_key': account_key})
        out = []
        for u in users:
            uu = normalize_doc(u)
            uid = uu.get('user_key') or uu.get('_id')
            user_obj = {
                'id': uid,
                'email': uu.get('email'),
                'name': _display_name(uu) or uu.get('name'),
                'role': _primary_role(uu),
                'phone': uu.get('phone'),
                'avatar': uu.get('avatar'),
                'permissions': uu.get('permissions') or uu.get('actions') or [],
                'createdAt': uu.get('created_at'),
                'lastLogin': uu.get('last_login'),
                'managerId': uu.get('manager_id')
            }
            out.append(user_obj)
        return respond_success({'users': out})
    except Exception:
        current_app.logger.exception('Error in api_list_users')
        return respond_error('Server error', status=500)

@user_api_bp.route('/users/<user_id>', methods=['GET'])
def api_get_user(user_id):
    try:
        payload = get_request_payload()
        u = user_repo.find_one({'user_key': user_id, 'account_key': payload.get('account_key')}) or user_repo.find_one({'_id': user_id})
        if not u:
            return respond_error('User not found', status=404)
        uu = normalize_doc(u)
        uid = uu.get('user_key') or uu.get('_id')
        user_obj = {
            'id': uid,
            'email': uu.get('email'),
            'name': _display_name(uu) or uu.get('name'),
            'role': _primary_role(uu),
            'phone': uu.get('phone'),
            'avatar': uu.get('avatar'),
            'permissions': uu.get('permissions') or uu.get('actions') or [],
            'createdAt': uu.get('created_at'),
            'lastLogin': uu.get('last_login'),
            'managerId': uu.get('manager_id')
        }
        return respond_success({'user': user_obj})
    except Exception:
        current_app.logger.exception('Error in api_get_user')
        return respond_error('Server error', status=500)

@user_api_bp.route('/users', methods=['POST'])
def api_create_user():
    try:
        payload = get_request_payload()
        data = request.get_json(force=True)
        try:
            user_doc = build_user(data, account_key=payload.get('account_key'))
        except Exception as e:
            current_app.logger.exception('Validation error in build_user')
            return respond_error(str(e), status=400)
        inserted_id = user_repo.create(user_doc)
        out = normalize_doc(user_doc)
        uid = user_doc.get('user_key') or str(inserted_id)
        user_obj = {
            'id': uid,
            'email': out.get('email'),
            'name': _display_name(out) or out.get('name'),
            'role': _primary_role(out),
            'phone': out.get('phone'),
            'avatar': out.get('avatar'),
            'permissions': out.get('permissions') or out.get('actions') or [],
            'createdAt': out.get('created_at'),
            'lastLogin': out.get('last_login'),
            'managerId': out.get('manager_id')
        }
        return respond_success({'user': user_obj})
    except Exception:
        current_app.logger.exception('Error in api_create_user')
        return respond_error('Server error', status=500)

@user_api_bp.route('/users/<user_id>', methods=['PATCH'])
def api_patch_user(user_id):
    try:
        payload = get_request_payload()
        data = request.get_json(force=True)
        res = user_repo.update({'user_key': user_id, 'account_key': payload.get('account_key')}, data)
        return respond_success({'updated': True})
    except Exception:
        current_app.logger.exception('Error in api_patch_user')
        return respond_error('Server error', status=500)

@user_api_bp.route('/users/<user_id>', methods=['DELETE'])
def api_delete_user(user_id):
    try:
        payload = get_request_payload()
        res = user_repo.delete({'user_key': user_id, 'account_key': payload.get('account_key')})
        return respond_success({'deleted': True})
    except Exception:
        current_app.logger.exception('Error in api_delete_user')
        return respond_error('Server error', status=500)
