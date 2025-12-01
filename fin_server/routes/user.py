from flask import Blueprint, request, jsonify
from fin_server.dto.user_dto import UserDTO
from fin_server.security.authentication import AuthSecurity
from fin_server.repository.user_repository import mongo_db_repository
import logging
import base64

user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/profile', methods=['GET'])
def get_profile():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        user_dto = UserDTO.find_by_user_key(user_key, account_key)
        if not user_dto:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        # Validate user is not logged out (must have valid refresh tokens)
        if not user_dto.refresh_tokens:
            return jsonify({'success': False, 'error': 'User is logged out'}), 401
        profile = user_dto.to_dict()
        profile.pop('password', None)
        profile.pop('refresh_tokens', None)
        return jsonify({'success': True, 'profile': profile}), 200
    except ValueError as ve:
        msg = str(ve).lower()
        if 'expired' in msg:
            logging.warning(f"Token expired: {ve}")
            return jsonify({'success': False, 'error': 'Token expired'}), 401
        if 'invalid token' in msg or 'signature' in msg or 'decode' in msg:
            logging.warning(f"Invalid token: {ve}")
            return jsonify({'success': False, 'error': 'Invalid token'}), 401
        logging.exception("ValueError in get_profile")
        return jsonify({'success': False, 'error': str(ve)}), 401
    except Exception as e:
        logging.exception("Error in get_profile")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@user_bp.route('/profile', methods=['PUT'])
def update_profile():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        user_dto = UserDTO.find_by_user_key(user_key, account_key)
        if not user_dto:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        # Validate user is not logged out (must have valid refresh tokens)
        if not user_dto.refresh_tokens:
            return jsonify({'success': False, 'error': 'User is logged out'}), 401
        data = request.get_json(force=True)
        profile_fields = ['first_name', 'last_name', 'dob', 'address1', 'address2', 'pincode', 'timezone']
        profile_data = {k: data[k] for k in profile_fields if k in data}
        # Update timezone in settings if provided
        if 'timezone' in profile_data:
            user_dto.settings['timezone'] = profile_data['timezone']
        user_dto.save_profile(profile_data)
        return jsonify({'success': True, 'message': 'Profile updated'}), 200
    except ValueError as ve:
        msg = str(ve).lower()
        if 'expired' in msg:
            logging.warning(f"Token expired: {ve}")
            return jsonify({'success': False, 'error': 'Token expired'}), 401
        if 'invalid token' in msg or 'signature' in msg or 'decode' in msg:
            logging.warning(f"Invalid token: {ve}")
            return jsonify({'success': False, 'error': 'Invalid token'}), 401
        logging.exception("ValueError in update_profile")
        return jsonify({'success': False, 'error': str(ve)}), 401
    except Exception as e:
        logging.exception("Error in update_profile")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@user_bp.route('/password', methods=['PUT'])
def update_password():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        user_dto = UserDTO.find_by_user_key(user_key, account_key)
        if not user_dto:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        # Validate user is not logged out (must have valid refresh tokens)
        if not user_dto.refresh_tokens:
            return jsonify({'success': False, 'error': 'User is logged out'}), 401
        data = request.get_json(force=True)
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        if not old_password or not new_password:
            return jsonify({'success': False, 'error': 'Missing password fields'}), 400
        db_password = base64.b64decode(user_dto.password.encode('utf-8')).decode('utf-8') if user_dto.password else ''
        if db_password != old_password:
            return jsonify({'success': False, 'error': 'Old password incorrect'}), 403
        user_dto.password = base64.b64encode(new_password.encode('utf-8')).decode('utf-8')
        user_dto.save()
        return jsonify({'success': True, 'message': 'Password updated'}), 200
    except ValueError as ve:
        msg = str(ve).lower()
        if 'expired' in msg:
            logging.warning(f"Token expired: {ve}")
            return jsonify({'success': False, 'error': 'Token expired'}), 401
        if 'invalid token' in msg or 'signature' in msg or 'decode' in msg:
            logging.warning(f"Invalid token: {ve}")
            return jsonify({'success': False, 'error': 'Invalid token'}), 401
        logging.exception("ValueError in update_password")
        return jsonify({'success': False, 'error': str(ve)}), 401
    except Exception as e:
        logging.exception("Error in update_password")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@user_bp.route('/logout', methods=['POST'])
def logout():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        user_dto = UserDTO.find_by_user_key(user_key, account_key)
        if not user_dto:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        user_dto._refresh_tokens = []
        user_dto._refresh_token_cache = set()
        user_dto.save()
        return jsonify({'success': True, 'message': 'Logged out'}), 200
    except ValueError as ve:
        msg = str(ve).lower()
        if 'expired' in msg:
            logging.warning(f"Token expired: {ve}")
            return jsonify({'success': False, 'error': 'Token expired'}), 401
        if 'invalid token' in msg or 'signature' in msg or 'decode' in msg:
            logging.warning(f"Invalid token: {ve}")
            return jsonify({'success': False, 'error': 'Invalid token'}), 401
        logging.exception("ValueError in logout")
        return jsonify({'success': False, 'error': str(ve)}), 401
    except Exception as e:
        logging.exception("Error in logout")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@user_bp.route('/settings', methods=['PUT'])
def update_settings():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        user_dto = UserDTO.find_by_user_key(user_key, account_key)
        if not user_dto:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        # Validate user is not logged out (must have valid refresh tokens)
        if not user_dto.refresh_tokens:
            return jsonify({'success': False, 'error': 'User is logged out'}), 401
        data = request.get_json(force=True)
        if 'settings' in data:
            user_dto.settings = data['settings']
            user_dto.save()
        return jsonify({'success': True, 'message': 'Settings updated'}), 200
    except ValueError as ve:
        msg = str(ve).lower()
        if 'expired' in msg:
            logging.warning(f"Token expired: {ve}")
            return jsonify({'success': False, 'error': 'Token expired'}), 401
        if 'invalid token' in msg or 'signature' in msg or 'decode' in msg:
            logging.warning(f"Invalid token: {ve}")
            return jsonify({'success': False, 'error': 'Invalid token'}), 401
        logging.exception("ValueError in update_settings")
        return jsonify({'success': False, 'error': str(ve)}), 401
    except Exception as e:
        logging.exception("Error in update_settings")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@user_bp.route('/settings/notifications', methods=['PUT'])
def update_notification_settings():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        user_dto = UserDTO.find_by_user_key(user_key, account_key)
        if not user_dto:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        # Validate user is not logged out (must have valid refresh tokens)
        if not user_dto.refresh_tokens:
            return jsonify({'success': False, 'error': 'User is logged out'}), 401
        data = request.get_json(force=True)
        if 'notifications' in data:
            user_dto.settings['notifications'] = data['notifications']
            user_dto.save()
        return jsonify({'success': True, 'message': 'Notification settings updated'}), 200
    except ValueError as ve:
        msg = str(ve).lower()
        if 'expired' in msg:
            logging.warning(f"Token expired: {ve}")
            return jsonify({'success': False, 'error': 'Token expired'}), 401
        if 'invalid token' in msg or 'signature' in msg or 'decode' in msg:
            logging.warning(f"Invalid token: {ve}")
            return jsonify({'success': False, 'error': 'Invalid token'}), 401
        logging.exception("ValueError in update_notification_settings")
        return jsonify({'success': False, 'error': str(ve)}), 401
    except Exception as e:
        logging.exception("Error in update_notification_settings")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@user_bp.route('/settings/help_support', methods=['PUT'])
def update_help_support():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        user_dto = UserDTO.find_by_user_key(user_key, account_key)
        if not user_dto:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        # Validate user is not logged out (must have valid refresh tokens)
        if not user_dto.refresh_tokens:
            return jsonify({'success': False, 'error': 'User is logged out'}), 401
        data = request.get_json(force=True)
        if 'help_support' in data:
            user_dto.settings['help_support'] = data['help_support']
            user_dto.save()
        return jsonify({'success': True, 'message': 'Help & support updated'}), 200
    except ValueError as ve:
        msg = str(ve).lower()
        if 'expired' in msg:
            logging.warning(f"Token expired: {ve}")
            return jsonify({'success': False, 'error': 'Token expired'}), 401
        if 'invalid token' in msg or 'signature' in msg or 'decode' in msg:
            logging.warning(f"Invalid token: {ve}")
            return jsonify({'success': False, 'error': 'Invalid token'}), 401
        logging.exception("ValueError in update_help_support")
        return jsonify({'success': False, 'error': str(ve)}), 401
    except Exception as e:
        logging.exception("Error in update_help_support")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@user_bp.route('/list', methods=['GET'])
def list_users():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        account_key = payload.get('account_key')
        if not account_key:
            return jsonify({'success': False, 'error': 'Missing account_key'}), 400
        users = mongo_db_repository.find_many('users', {'account_key': account_key})
        show_phone = request.args.get('phone', 'false').lower() == 'true'
        filtered_users = []
        for u in users:
            user_obj = {
                'user_key': u.get('user_key'),
                'username': u.get('username'),
                'roles': u.get('roles', []),
                'account_key': u.get('account_key'),
                'email': u.get('email')
            }
            if show_phone:
                user_obj['phone'] = u.get('phone')
            filtered_users.append(user_obj)
        return jsonify({'success': True, 'users': filtered_users}), 200
    except Exception as e:
        logging.exception('Error in list_users')
        return jsonify({'success': False, 'error': 'Server error'}), 500

@user_bp.route('/account/<account_key>/user/<user_key>', methods=['DELETE'])
def delete_user(account_key, user_key):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        roles = payload.get('roles', [])
        if 'admin' not in roles or payload.get('account_key') != account_key:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        deleted_count = mongo_db_repository.delete('users', {'account_key': account_key, 'user_key': user_key})
        if deleted_count > 0:
            return jsonify({'success': True, 'message': 'User deleted'}), 200
        else:
            return jsonify({'success': False, 'error': 'User not found'}), 404
    except Exception as e:
        logging.exception('Error in delete_user')
        return jsonify({'success': False, 'error': 'Server error'}), 500
