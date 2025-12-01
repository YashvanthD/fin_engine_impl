import datetime

from flask import Blueprint, request, jsonify
from fin_server.utils.validation import validate_signup, validate_signup_user
from fin_server.repository.user_repository import mongo_db_repository
from fin_server.utils.generator import generate_key, build_user
from fin_server.response.auth_response import build_user_response, build_token_only_response, build_signup_login_response
from fin_server.security.authentication import AuthSecurity
from fin_server.dto.user_dto import UserDTO
from fin_server.requests.subscription import default_subscription
import time
import logging
import base64

# Blueprint for auth routes
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Authentication Endpoints
@auth_bp.route('/signup', methods=['POST'])
def signup():
    logging.info("Signup endpoint called")
    data = request.get_json(force=True)
    logging.info("Received signup data: %s", data)
    is_valid, errors = validate_signup(data)
    logging.info("Signup validation result: %s", is_valid)
    if not is_valid:
        logging.warning("Signup validation failed: %s", errors)
        return jsonify({'success': False, 'errors': errors}), 400
    data['roles']=['admin']
    admin_data = build_user(data)
    logging.info("Built admin data: %s", admin_data)
    user_id = mongo_db_repository.create("users", admin_data)
    logging.info("Admin user created with ID: %s", user_id)
    response = build_signup_login_response(success=True, message='Admin signup validated and saved.', user_id=user_id,
                                           account_key=admin_data['account_key'], user_key=admin_data['user_key'])
    logging.info("Signup response: %s", response)
    return jsonify(response), 201

@auth_bp.route('/account/<account_key>/signup', methods=['POST'])
def signup_user(account_key):
    logging.info("Account signup endpoint called for account_key: %s", account_key)
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        logging.warning("Missing or invalid admin token")
        return jsonify({'success': False, 'error': 'Missing or invalid admin token'}), 401
    admin_token = auth_header.split(' ', 1)[1]
    logging.info("Validating admin token for account signup")
    is_admin_valid = AuthSecurity.validate_role_token(
        mongo_db_repository, 'users', admin_token, required_role='admin', account_key=account_key
    )
    logging.info("Admin token validation result: %s", is_admin_valid)
    if not is_admin_valid:
        logging.warning("Unauthorized admin token or role/account_key")
        return jsonify({'success': False, 'error': 'Unauthorized: Invalid admin token, role, or account_key'}), 401
    data = request.get_json(force=True)
    logging.info("Received user signup data: %s", data)
    is_valid, errors = validate_signup_user(data, account_key)
    logging.info("User signup validation result: %s", is_valid)
    if not is_valid:
        logging.warning("User signup validation failed: %s", errors)
        return jsonify({'success': False, 'errors': errors}), 400
    user_data = build_user(data, account_key)
    logging.info("Built user data: %s", user_data)
    user_id = mongo_db_repository.create("users", user_data)
    logging.info("User created with ID: %s", user_id)
    response = build_signup_login_response(success=True, message='User signup validated and saved.', user_id=user_id,
                                           account_key=account_key, user_key=user_data['user_key'])
    logging.info("Account signup response: %s", response)
    return jsonify(response), 201

# Helper: Load user DTO from DB or cache
def load_user_dto_by_username(username):
    user_doc = mongo_db_repository.find_one("users", {"username": username})
    if not user_doc:
        return None, None
    user_dto = UserDTO.get_from_cache(user_doc['user_key'])
    if not user_dto:
        user_dto = UserDTO(
            user_id=user_doc.get('_id'),
            account_key=user_doc.get('account_key'),
            user_key=user_doc.get('user_key'),
            roles=user_doc.get('roles'),
            refresh_tokens=user_doc.get('refresh_tokens'),
            **{k: v for k, v in user_doc.items() if k not in {"_id", "account_key", "user_key", "roles", "refresh_tokens"}}
        )
    return user_doc, user_dto

# Helper: Load user DTO from DB or cache by username, phone, or email
def load_user_dto_by_identifier(username=None, phone=None, email=None):
    query = {}
    if username:
        query['username'] = username
    if phone:
        query['phone'] = phone
    if email:
        query['email'] = email
    if not query:
        return None, None
    user_doc = mongo_db_repository.find_one("users", query)
    if not user_doc:
        return None, None
    user_dto = UserDTO.get_from_cache(user_doc.get('user_key') or user_doc.get('user_key'))
    if not user_dto:
        # Normalize keys: always use snake_case and only 'account_key', 'user_key'
        user_doc_clean = {}
        for k, v in user_doc.items():
            if k == '_id':
                user_doc_clean['user_id'] = v
            elif k.lower() == 'account_key':
                user_doc_clean['account_key'] = v
            elif k.lower() == 'user_key':
                user_doc_clean['user_key'] = v
            else:
                user_doc_clean[k.lower()] = v
        # Ensure required keys exist
        if 'account_key' not in user_doc_clean or 'user_key' not in user_doc_clean:
            return None, None
        user_dto = UserDTO(**user_doc_clean)
    return user_doc, user_dto

# Helper: Validate password
def validate_password(db_password, password):
    if db_password:
        try:
            db_password = base64.b64decode(db_password.encode('utf-8')).decode('utf-8')
        except Exception:
            pass
    return db_password == password

# Helper: Build token payload
def build_access_payload(user_dto):
    return {
        'user_key': user_dto.user_key,
        'account_key': user_dto.account_key,
        'roles': user_dto.roles,
        'type': 'access'
    }



# Helper: Build response
def build_user_response(user_dto, access_token=None, refresh_token=None):
    user_dict = user_dto.to_dict()
    user_dict.pop('password', None)
    user_dict.pop('refresh_tokens', None)
    response = {
        'success': True,
        'user_key': user_dto.user_key,
        'account_key': user_dto.account_key,
        'roles': user_dto.roles,
        'settings': user_dto.settings,
        'subscription': user_dto.subscription,
        'user': {k: v for k, v in user_dict.items() if k not in ['password', 'refresh_tokens']}
    }
    if access_token:
        response['access_token'] = access_token
    if refresh_token:
        response['refresh_token'] = refresh_token
    return response

def handle_login_or_token_request(username=None, password=None, refresh_token=None, phone=None, email=None, expires_in=None):
    logging.info("Handling login/token request")
    user_dto = None
    # Case 1: Use refresh token
    if refresh_token:
        logging.info("Attempting token generation from refresh token")
        try:
            payload = AuthSecurity.decode_token(refresh_token)
            user_key = payload.get('user_key')
            account_key = payload.get('account_key')
            user_dto = UserDTO.find_by_user_key(user_key)
            if not user_dto or user_dto.account_key != account_key:
                logging.warning("User not found for user_key: %s, account_key: %s", user_key, account_key)
                return {'success': False, 'error': 'User not found'}, 404
            # Cleanup expired refresh tokens before validating
            AuthSecurity.validate_and_cleanup_refresh_tokens(user_dto, create_new=False)
            valid = AuthSecurity.validate_refresh_token(mongo_db_repository, 'users', user_key, refresh_token)
            if not valid:
                logging.warning("Invalid or expired refresh token")
                return {'success': False, 'error': 'Invalid or expired refresh token'}, 401
            expires_delta = None
            if expires_in:
                try:
                    expires_delta = datetime.timedelta(seconds=int(expires_in))
                except Exception:
                    logging.warning("Invalid expires_in param: %s", expires_in)
            access_token = AuthSecurity.encode_token(build_access_payload(user_dto), expires_delta=expires_delta)
            logging.info("Access token generated from refresh token")
            response = build_user_response(user_dto, access_token=access_token)
            return response, 200
        except ValueError as ve:
            logging.warning("Token validation error: %s", ve)
            return {'success': False, 'error': str(ve)}, 401
        except Exception as e:
            logging.exception("Exception in token generation from refresh token")
            return {'success': False, 'error': 'Server error'}, 500
    # Case 2: Use username, phone, or email + password
    elif (username or phone or email) and password:
        logging.info("Attempting token generation from username/phone/email/password")
        user_doc, user_dto = load_user_dto_by_identifier(username=username, phone=phone, email=email)
        if not user_doc or not user_dto:
            logging.warning("Invalid credentials: user not found")
            return {'success': False, 'error': 'Invalid credentials'}, 401
        if not validate_password(user_doc.get('password'), password):
            logging.warning("Invalid credentials: password mismatch")
            return {'success': False, 'error': 'Invalid credentials'}, 401
        user_dto.touch()
        # Cleanup expired refresh tokens before creating new one
        AuthSecurity.validate_and_cleanup_refresh_tokens(user_dto, create_new=False)
        expires_delta = None
        if expires_in:
            try:
                expires_delta = datetime.timedelta(seconds=int(expires_in))
            except Exception:
                logging.warning("Invalid expires_in param: %s", expires_in)
        access_token = AuthSecurity.encode_token(build_access_payload(user_dto), expires_delta=expires_delta)
        # Always create a new refresh token for password login
        new_refresh_token = AuthSecurity.create_refresh_token({
            'user_key': user_dto.user_key,
            'account_key': user_dto.account_key,
            'roles': user_dto.roles,
            'type': 'refresh'
        })
        user_dto.add_refresh_token(new_refresh_token)
        mongo_db_repository.update("users", {"user_key": user_dto.user_key}, user_dto.to_dict())
        response = build_user_response(user_dto, access_token=access_token, refresh_token=new_refresh_token)
        logging.info("Token generation response: %s", response)
        return response, 200
    else:
        logging.warning("No valid credentials or refresh token provided")
        return {'success': False, 'error': 'Provide either refresh_token or username/phone/email/password'}, 400

@auth_bp.route('/login', methods=['POST'])
def login():
    logging.info("Login endpoint called")
    data = request.get_json(force=True)
    username = data.get('username')
    password = data.get('password')
    phone = data.get('phone')
    email = data.get('email')
    response, status = handle_login_or_token_request(username=username, password=password, phone=phone, email=email)
    return jsonify(response), status

# User Data Endpoints
@auth_bp.route('/account/users', methods=['GET'])
def list_account_users():
    logging.info("List account users endpoint called")
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        logging.warning("Missing or invalid token")
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        logging.info("Token validated: %s", payload)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        roles = payload.get('roles', [])
        if 'admin' in roles:
            logging.info("Admin role detected, fetching all users for account_key: %s", account_key)
            user_list = UserDTO.find_many_by_account(account_key)
            logging.info("Fetched users: %d", len(user_list))
            return jsonify({'success': True, 'users': user_list}), 200
        else:
            logging.info("User role detected, fetching self for user_key: %s", user_key)
            user_dto = UserDTO.find_by_user_key(user_key)
            if not user_dto or user_dto.account_key != account_key:
                logging.warning("User not found for user_key: %s, account_key: %s", user_key, account_key)
                return jsonify({'success': False, 'error': 'User not found'}), 404
            logging.info("Fetched user: %s", user_dto.to_dict())
            return jsonify({'success': True, 'user': user_dto.to_dict()}), 200
    except Exception as e:
        logging.exception("Exception in list_account_users endpoint")
        return jsonify({'success': False, 'error': 'Invalid token or server error'}), 401

@auth_bp.route('/settings', methods=['GET', 'PUT'])
def user_settings():
    logging.info("Settings endpoint called")
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        logging.warning("Missing or invalid token")
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
    except Exception as e:
        logging.exception("Token decode error in /settings endpoint")
        return jsonify({'success': False, 'error': 'Invalid token or server error'}), 401
    user_key = payload.get('user_key')
    account_key = payload.get('account_key')
    try:
        logging.info("Fetching userDTO for user_key: %s", user_key)
        user_dto = UserDTO.find_by_user_key(user_key)
        if not user_dto or user_dto.account_key != account_key:
            logging.warning("User not found for user_key: %s, account_key: %s", user_key, account_key)
            return jsonify({'success': False, 'error': 'User not found'}), 404
        if request.method == 'PUT':
            updated_settings = request.get_json(force=True).get('settings', {})
            logging.info("Updating settings for user_key: %s", user_key)
            user_dto.settings = updated_settings
            user_dto.save()
            logging.info("Settings updated and saved for user_key: %s", user_key)
        logging.info("Returning settings and subscription for user_key: %s", user_key)
        return jsonify({
            'user_key': user_key,
            'account_key': account_key,
            'settings': user_dto.settings,
            'subscription': user_dto.subscription
        }), 200
    except Exception as e:
        logging.exception("Exception in /settings endpoint")
        return jsonify({'success': False, 'error': 'Server error'}), 500



@auth_bp.route('/permissions', methods=['GET'])
def get_user_permissions():
    # TODO: Implement get user permissions
    return jsonify({'message': 'Get user permissions endpoint'}), 200

@auth_bp.route('/validate', methods=['GET'])
def validate_token():
    logging.info("Validate token endpoint called")
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        logging.warning("Missing or invalid token")
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        logging.info("Token validated: %s", payload)
        # Check expiry in payload (already handled in decode_token, but log for clarity)
        exp = payload.get('exp')
        if exp is not None:
            now = int(time.time())
            if isinstance(exp, datetime.datetime):
                exp = int(exp.timestamp())
            elif isinstance(exp, float):
                exp = int(exp)
            if exp < now:
                logging.warning("Token expired at %s", exp)
                return jsonify({'success': False, 'error': 'Token expired'}), 401
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        user_dto = UserDTO.find_by_user_key(user_key)
        if not user_dto or user_dto.account_key != account_key:
            logging.warning("User not found for user_key: %s, account_key: %s", user_key, account_key)
            return jsonify({'success': False, 'error': 'User not found'}), 404
        user_dict = user_dto.to_dict()
        # Remove sensitive fields
        user_dict.pop('password', None)
        user_dict.pop('refresh_tokens', None)
        # Build response
        response = {
            'success': True,
            'user_key': user_dto.user_key,
            'account_key': user_dto.account_key,
            'roles': user_dto.roles,
            'settings': user_dto.settings,
            'subscription': user_dto.subscription,
            'last_active': user_dto.last_active
        }
        logging.info("Validate response: %s", response)
        return jsonify(response), 200
    except ValueError as ve:
        logging.warning("Token validation error: %s", ve)
        return jsonify({'success': False, 'error': str(ve)}), 401
    except Exception as e:
        logging.exception("Exception in validate_token endpoint")
        return jsonify({'success': False, 'error': 'Invalid token or server error'}), 401

def build_token_only_response(access_token, expires_in=None):
    response = {
        'access_token': access_token
    }
    if expires_in:
        response['expires_in'] = expires_in
    return response

@auth_bp.route('/token', methods=['POST'])
def generate_token():
    logging.info("Token generation endpoint called")
    data = request.get_json(force=True)
    token_type = data.get('type', 'access_token')
    refresh_token = data.get('refresh_token')
    token = data.get('token')  # for refresh_token flow
    username = data.get('username')
    password = data.get('password')
    phone = data.get('phone')
    email = data.get('email')
    expires_in = data.get('expires_in')

    # If type is 'refresh_token' and token is provided, generate access token from refresh token
    if token_type == 'refresh_token' and token:
        try:
            payload = AuthSecurity.decode_token(token)
            user_key = payload.get('user_key')
            account_key = payload.get('account_key')
            user_dto = UserDTO.find_by_user_key(user_key)
            if not user_dto or user_dto.account_key != account_key:
                logging.warning("User not found for user_key: %s, account_key: %s", user_key, account_key)
                return jsonify({'success': False, 'error': 'User not found'}), 404
            valid = AuthSecurity.validate_refresh_token(mongo_db_repository, 'users', user_key, token)
            if not valid:
                logging.warning("Invalid or expired refresh token")
                return jsonify({'success': False, 'error': 'Invalid or expired refresh token'}), 401
            expires_delta = None
            if expires_in:
                try:
                    expires_delta = datetime.timedelta(seconds=int(expires_in))
                except Exception:
                    logging.warning("Invalid expires_in param: %s", expires_in)
            access_token = AuthSecurity.encode_token({
                'user_key': user_dto.user_key,
                'account_key': user_dto.account_key,
                'roles': user_dto.roles,
                'type': 'access'
            }, expires_delta=expires_delta)
            # Calculate expiry timestamp
            expiry = None
            if expires_delta:
                expiry = int(time.time()) + int(expires_in)
            response = build_token_only_response(access_token, expiry)
            logging.info("Access token generated from refresh token: %s", response)
            return jsonify(response), 200
        except ValueError as ve:
            logging.warning("Token validation error: %s", ve)
            return jsonify({'success': False, 'error': str(ve)}), 401
        except Exception as e:
            logging.exception("Exception in token generation from refresh token")
            return jsonify({'success': False, 'error': 'Server error'}), 500
    # If type is 'refresh_token' and password+identifier is provided, generate new refresh token
    elif token_type == 'refresh_token':
        if not password or not (username or phone or email):
            logging.warning("Missing password or user identifier for refresh_token type")
            return jsonify({'success': False, 'error': 'Password and user identifier required for refresh_token'}), 400
        user_doc, user_dto = load_user_dto_by_identifier(username=username, phone=phone, email=email)
        if not user_doc or not user_dto:
            logging.warning("Invalid credentials: user not found")
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        if not validate_password(user_doc.get('password'), password):
            logging.warning("Invalid credentials: password mismatch")
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        user_dto.touch()
        refresh_payload = {
            'user_key': user_dto.user_key,
            'account_key': user_dto.account_key,
            'roles': user_dto.roles,
            'type': 'refresh'
        }
        expires_delta = None
        if expires_in:
            try:
                expires_delta = datetime.timedelta(seconds=int(expires_in))
            except Exception:
                logging.warning("Invalid expires_in param: %s", expires_in)
        refresh_token_val = AuthSecurity.create_refresh_token(refresh_payload)
        user_dto.add_refresh_token(refresh_token_val)
        mongo_db_repository.update("users", {"user_key": user_dto.user_key}, user_dto.to_dict())
        # Only return refresh token and expiry
        expiry = None
        if expires_delta:
            expiry = int(time.time()) + int(expires_in)
        response = {'refresh_token': refresh_token_val}
        if expiry:
            response['expires_in'] = expiry
        logging.info("Refresh token generated and response: %s", response)
        return jsonify(response), 200
    else:
        # Default: access token flow (existing logic)
        response, status = handle_login_or_token_request(username=username, password=password, refresh_token=refresh_token, phone=phone, email=email, expires_in=expires_in)
        # Only return access token and expiry
        if response.get('access_token'):
            expiry = None
            if expires_in:
                expiry = int(time.time()) + int(expires_in)
            response = build_token_only_response(response['access_token'], expiry)
        return jsonify(response), status

@auth_bp.route('/subscriptions', methods=['GET', 'PUT'])
def user_subscriptions():
    logging.info("Subscriptions endpoint called")
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        logging.warning("Missing or invalid token")
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
    except Exception as e:
        logging.exception("Token decode error in /subscriptions endpoint")
        return jsonify({'success': False, 'error': 'Invalid token or server error'}), 401
    user_key = payload.get('user_key')
    account_key = payload.get('account_key')
    roles = payload.get('roles', [])
    try:
        logging.info("Fetching userDTO for user_key: %s", user_key)
        user_dto = UserDTO.find_by_user_key(user_key)
        if not user_dto or user_dto.account_key != account_key:
            logging.warning("User not found for user_key: %s, account_key: %s", user_key, account_key)
            return jsonify({'success': False, 'error': 'User not found'}), 404
        if request.method == 'PUT':
            if 'admin' not in roles:
                logging.warning("Non-admin tried to update subscriptions")
                return jsonify({'success': False, 'error': 'Only admin can update subscriptions'}), 403
            updated_subscription = request.get_json(force=True).get('subscription', {})
            logging.info("Admin updating subscription for account_key: %s", account_key)
            # Update subscription for all users in the account
            users = UserDTO.find_many_by_account(account_key)
            for user in users:
                dto = UserDTO.find_by_user_key(user['user_key'], account_key)
                if dto:
                    dto.subscription = updated_subscription
                    dto.save()
            logging.info("Subscription updated for all users in account_key: %s", account_key)
        # Always return current user's subscription
        logging.info("Returning subscription for user_key: %s", user_key)
        subscription = user_dto.subscription or {}
        if 'admin' in roles:
            # Admin sees full subscription info
            resp_subscription = subscription
        else:
            # User sees only type and expiry
            resp_subscription = {
                'subscription_type': subscription.get('subscription_type', ''),
                'expiry': subscription.get('expiry', '')
            }
        return jsonify({
            'user_key': user_key,
            'account_key': account_key,
            'subscription': resp_subscription
        }), 200
    except Exception as e:
        logging.exception("Exception in /subscriptions endpoint")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@auth_bp.route('/account/<account_key>/company', methods=['GET'])
def get_company_name(account_key):
    from fin_server.repository.user_repository import mongo_db_repository
    # Find any admin user for this account_key
    admin_doc = mongo_db_repository.get_collection('users').find_one({
        'account_key': account_key,
        'roles': {'$in': ['admin']}
    })
    if admin_doc and 'company_name' in admin_doc:
        return jsonify({'success': True, 'company_name': admin_doc['company_name']}), 200
    return jsonify({'success': False, 'error': 'Company not found'}), 404
