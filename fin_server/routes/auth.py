import base64
import datetime
import hmac
import logging
import os
import time

from flask import Blueprint, request, current_app

from fin_server.dto.user_dto import UserDTO
from fin_server.repository.mongo_helper import get_collection
from fin_server.security.authentication import AuthSecurity, get_auth_payload
from fin_server.utils.generator import build_user
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc
from fin_server.utils.validation import validate_signup, validate_signup_user, build_signup_login_response

# In production, MASTER_ADMIN_PASSWORD must be provided via environment variables.
# In development (FLASK_DEBUG=true), a weak default is allowed for convenience.
_FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes')
MASTER_ADMIN_PASSWORD = os.getenv('MASTER_ADMIN_PASSWORD')
if not MASTER_ADMIN_PASSWORD and _FLASK_DEBUG:
    MASTER_ADMIN_PASSWORD = 'password'


def _encode_password_legacy(pwd: str) -> str:
    """Legacy base64 encoding for passwords (for migration only)."""
    return base64.b64encode(pwd.encode('utf-8')).decode('utf-8')


def _check_password_migrating(plain: str, stored: str):
    """Check password against stored hash, supporting legacy base64.

    Returns (ok, new_hash_or_none). If ok is True and new_hash_or_none is not
    None, caller may choose to upgrade the stored password to a stronger hash.
    This helper does not perform the DB update itself.
    """
    # bcrypt hashes are not handled here anymore; higher-level code should
    # treat non-base64 values as final and just compare directly if needed.
    try:
        if _encode_password_legacy(plain) == stored:
            # In this project we historically stored base64(password). To keep
            # behaviour compatible, a match is enough; no new hash is produced.
            return True, None
    except Exception:
        pass
    return False, None

# Blueprint for auth routes
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

user_repo = get_collection('users')

# Authentication Endpoints
@auth_bp.route('/signup', methods=['POST'])
def signup():
    logging.info("Signup endpoint called")
    current_app.logger.info('POST /auth/signup called')
    data = request.get_json(force=True)
    current_app.logger.info(f'Received signup data: {data}')
    provided_master = data.get('master_password')
    # If master password is configured and provided, enforce it for privileged admin/company bootstrap
    if not(provided_master is None or provided_master ==  ""):
        if MASTER_ADMIN_PASSWORD is None:
            logging.error("MASTER_ADMIN_PASSWORD is not configured in environment")
            return respond_error('Server not configured for admin registration', status=500)
        if (not(hmac.compare_digest(str(provided_master), str(MASTER_ADMIN_PASSWORD)) and not(provided_master == MASTER_ADMIN_PASSWORD))):
            logging.warning("Invalid master password provided for admin signup")
            return respond_error('Unauthorized: invalid master password', status=403)
        # Remove master_password from data before storing user
        data.pop('master_password', None)
    else:
        # No master_password provided: allow creation of a free-tier admin account.
        # This path is intended for public self‑service signup and should not require
        # MASTER_ADMIN_PASSWORD. We still remove any stray master_password field.
        data.pop('master_password', None)
        logging.info("No master_password provided, creating free subscription admin account")
    is_valid, errors = validate_signup(data)
    current_app.logger.info(f'Validation result: {is_valid}, errors: {errors}')
    logging.info("Signup validation result: %s", is_valid)
    if not is_valid:
        logging.warning("Signup validation failed: %s", errors)
        return respond_error(errors, status=400)
    # Ensure this user is an admin for the account
    data['roles'] = ['admin']
    # If no subscription explicitly present, mark subscription type as 'free'
    try:
        subscription = data.get('subscription') or {}
    except Exception:
        subscription = {}
    if 'subscription_type' not in subscription and 'type' not in subscription:
        subscription['subscription_type'] = 'free'
    data['subscription'] = subscription
    admin_data = build_user(data)
    logging.info("Built admin data: %s", admin_data)
    user_id = user_repo.create(admin_data)
    current_app.logger.info(f'Admin user created with ID: {user_id}')
    logging.info("Admin user created with ID: %s", user_id)
    response = build_signup_login_response(success=True, message='Admin signup validated and saved.', user_id=user_id,
                                           account_key=admin_data['account_key'], user_key=admin_data['user_key'])
    current_app.logger.info(f'Signup response: {response}')
    logging.info("Signup response: %s", response)
    return respond_success(response, status=201)

@auth_bp.route('/account/<account_key>/signup', methods=['POST'])
def signup_user(account_key):
    logging.info("Account signup endpoint called for account_key: %s", account_key)
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        logging.warning("Missing or invalid admin token")
        return respond_error('Missing or invalid admin token', status=401)
    admin_token = auth_header.split(' ', 1)[1]
    logging.info("Validating admin token for account signup")
    is_admin_valid = AuthSecurity.validate_role_token(
        user_repo, 'users', admin_token, required_role='admin', account_key=account_key
    )
    logging.info("Admin token validation result: %s", is_admin_valid)
    if not is_admin_valid:
        logging.warning("Unauthorized admin token or role/account_key")
        return respond_error('Unauthorized: Invalid admin token, role, or account_key', status=401)
    data = request.get_json(force=True)
    logging.info("Received user signup data: %s", data)
    is_valid, errors = validate_signup_user(data, account_key)
    logging.info("User signup validation result: %s", is_valid)
    if not is_valid:
        logging.warning("User signup validation failed: %s", errors)
        return respond_error(errors, status=400)
    user_data = build_user(data, account_key)
    logging.info("Built user data: %s", user_data)
    user_id = user_repo.create(user_data)
    logging.info("User created with ID: %s", user_id)
    response = build_signup_login_response(success=True, message='User signup validated and saved.', user_id=user_id,
                                           account_key=account_key, user_key=user_data['user_key'])
    logging.info("Account signup response: %s", response)
    return respond_success(response, status=201)

# Helper: Load user DTO from DB or cache
def load_user_dto_by_username(username):
    user_doc = user_repo.find_one({"username": username})
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
    user_doc = user_repo.find_one(query)
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
            valid = AuthSecurity.validate_refresh_token(user_repo, 'users', user_key, refresh_token)
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
        stored_pwd = user_doc.get('password') or ''
        ok, new_hash = _check_password_migrating(password, stored_pwd)
        if not ok:
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
        user_repo.update({"user_key": user_dto.user_key}, user_dto.to_dict())
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
    if status >= 400:
        return respond_error(response.get('error') or response.get('message') or response, status=status)
    return respond_success(response, status=status)

# User Data Endpoints
@auth_bp.route('/account/users', methods=['GET'])
def list_account_users():
    logging.info("List account users endpoint called")
    payload = get_auth_payload(request)
    user_key = payload.get('user_key')
    account_key = payload.get('account_key')
    roles = payload.get('roles', [])
    try:
        if 'admin' in roles:
            logging.info("Admin role detected, fetching all users for account_key: %s", account_key)
            user_list = UserDTO.find_many_by_account(account_key)
            logging.info("Fetched users: %d", len(user_list))
            return respond_success({'users': user_list})
        else:
            logging.info("User role detected, fetching self for user_key: %s", user_key)
            user_dto = UserDTO.find_by_user_key(user_key)
            if not user_dto or user_dto.account_key != account_key:
                logging.warning("User not found for user_key: %s, account_key: %s", user_key, account_key)
                return respond_error('User not found', status=404)
            logging.info("Fetched user: %s", user_dto.to_dict())
            return respond_success({'user': user_dto.to_dict()})
    except Exception as e:
        logging.exception("Exception in list_account_users endpoint")
        return respond_error('Invalid token or server error', status=401)

@auth_bp.route('/settings', methods=['GET', 'PUT'])
def user_settings():
    """Deprecated: use GET/PUT /user/settings instead.

    This endpoint is kept temporarily for backward compatibility. It
    simply proxies to the same data model as /user/settings so that
    clients can be migrated gradually.
    """
    logging.info("/auth/settings is deprecated; prefer /user/settings")
    payload = get_auth_payload(request)
    user_key = payload.get('user_key')
    account_key = payload.get('account_key')
    try:
        user_dto = UserDTO.find_by_user_key(user_key, account_key)
        if not user_dto:
            logging.warning("User not found for user_key: %s, account_key: %s", user_key, account_key)
            return respond_error('User not found', status=404)
        if request.method == 'PUT':
            body = request.get_json(force=True) or {}
            updated_settings = body.get('settings') or body
            logging.info("Updating settings via /auth/settings shim for user_key: %s", user_key)
            user_dto.settings = updated_settings
            user_dto.save()
        return respond_success({
            'user_key': user_dto.user_key,
            'account_key': user_dto.account_key,
            'settings': user_dto.settings,
            'subscription': user_dto.subscription
        })
    except Exception:
        logging.exception("Exception in deprecated /auth/settings endpoint")
        return respond_error('Server error', status=500)



@auth_bp.route('/permissions', methods=['GET'])
def get_user_permissions():
    # TODO: Implement get user permissions
    return respond_success({'message': 'Get user permissions endpoint'})

@auth_bp.route('/validate', methods=['GET'])
def validate_token():
    logging.info("Validate token endpoint called")
    payload = get_auth_payload(request)
    user_key = payload.get('user_key')
    account_key = payload.get('account_key')
    user_dto = UserDTO.find_by_user_key(user_key)
    if not user_dto or user_dto.account_key != account_key:
        logging.warning("User not found for user_key: %s, account_key: %s", user_key, account_key)
        return respond_error('User not found', status=404)
    user_dict = user_dto.to_dict()
    user_dict.pop('password', None)
    user_dict.pop('refresh_tokens', None)
    response = {
        'user_key': user_dto.user_key,
        'account_key': user_dto.account_key,
        'roles': user_dto.roles,
        'settings': user_dto.settings,
        'subscription': user_dto.subscription,
        'last_active': user_dto.last_active,
        'user': user_dict
    }
    logging.info("Validate response: %s", response)
    return respond_success(response)

@auth_bp.route('/me', methods=['GET'])
def auth_me():
    """Return the current authenticated user's core info.

    This endpoint is optimized for SPA clients that want a quick
    "who am I" check: it returns user_key, account_key, roles,
    settings, subscription, last_active, and a sanitized user object.
    """
    logging.info("/auth/me endpoint called")
    payload = get_auth_payload(request)
    user_key = payload.get('user_key')
    account_key = payload.get('account_key')
    user_dto = UserDTO.find_by_user_key(user_key)
    if not user_dto or user_dto.account_key != account_key:
        logging.warning("User not found for user_key: %s, account_key: %s", user_key, account_key)
        return respond_error('User not found', status=404)
    user_dict = user_dto.to_dict()
    user_dict.pop('password', None)
    user_dict.pop('refresh_tokens', None)
    response = {
        'user_key': user_dto.user_key,
        'account_key': user_dto.account_key,
        'roles': user_dto.roles,
        'settings': user_dto.settings,
        'subscription': user_dto.subscription,
        'last_active': user_dto.last_active,
        'user': user_dict
    }
    logging.info("/auth/me response: %s", response)
    return respond_success(response)

def build_token_only_response(access_token, expires_in=None):
    response = {
        'access_token': access_token
    }
    if expires_in:
        response['expires_in'] = str(expires_in)
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
        # Validate token format before decoding
        if not token or token.count('.') != 2:
            logging.warning("Malformed or missing refresh token in /auth/token endpoint")
            return {'success': False, 'error': 'Malformed or missing refresh token. Please provide a valid JWT refresh token.'}, 401
        try:
            payload = AuthSecurity.decode_token(token)
            user_key = payload.get('user_key')
            account_key = payload.get('account_key')
            user_dto = UserDTO.find_by_user_key(user_key)
            if not user_dto or user_dto.account_key != account_key:
                logging.warning("User not found for user_key: %s, account_key: %s", user_key, account_key)
                return {'success': False, 'error': 'User not found'}, 404
            valid = AuthSecurity.validate_refresh_token(user_repo, 'users', user_key, token)
            if not valid:
                logging.warning("Invalid or expired refresh token")
                return {'success': False, 'error': 'Invalid or expired refresh token'}, 401
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
                # expiry is stored as epoch seconds; frontend can render in IST via helpers
                expiry = int(time.time()) + int(expires_in)
            response = build_token_only_response(access_token, expiry)
            logging.info("Access token generated from refresh token: %s", response)
            return respond_success(response, status=200)
        except ValueError as ve:
            logging.warning("Token validation error: %s", ve)
            return {'success': False, 'error': str(ve)}, 401
        except Exception as e:
            logging.exception("Exception in token generation from refresh token")
            return {'success': False, 'error': 'Invalid or corrupted refresh token. Please login again.'}, 401
    # If type is 'refresh_token' and password+identifier is provided, generate new refresh token
    elif token_type == 'refresh_token':
        if not password or not (username or phone or email):
            logging.warning("Missing password or user identifier for refresh_token type")
            return {'success': False, 'error': 'Password and user identifier required for refresh_token'}, 400
        user_doc, user_dto = load_user_dto_by_identifier(username=username, phone=phone, email=email)
        if not user_doc or not user_dto:
            logging.warning("Invalid credentials: user not found")
            return {'success': False, 'error': 'Invalid credentials'}, 401
        if not validate_password(user_doc.get('password'), password):
            logging.warning("Invalid credentials: password mismatch")
            return {'success': False, 'error': 'Invalid credentials'}, 401
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
        user_repo.update({"user_key": user_dto.user_key}, user_dto.to_dict())
        # Only return refresh token and expiry
        expiry = None
        if expires_delta:
            # expiry is epoch seconds; UI converts to IST
            expiry = int(time.time()) + int(expires_in)
        response = {'refresh_token': refresh_token_val}
        if expiry:
            response['expires_in'] = str(expiry)
        logging.info("Refresh token generated and response: %s", response)
        return respond_success(response, status=200)
    else:
        # Default: access token flow (existing logic)
        response, status = handle_login_or_token_request(username=username, password=password, refresh_token=refresh_token, phone=phone, email=email, expires_in=expires_in)
        # Only return access token and expiry
        if response.get('access_token'):
            expiry = None
            if expires_in:
                # expiry is epoch seconds; UI converts to IST
                expiry = int(time.time()) + int(expires_in)
            response = build_token_only_response(response['access_token'], expiry)
        if status >= 400:
            return respond_error(response.get('error') or response.get('message') or response, status=status)
        return respond_success(response, status=status)

@auth_bp.route('/subscriptions', methods=['GET', 'PUT'])
def user_subscriptions():
    logging.info("Subscriptions endpoint called")
    payload = get_auth_payload(request)
    user_key = payload.get('user_key')
    account_key = payload.get('account_key')
    roles = payload.get('roles', [])
    try:
        logging.info("Fetching userDTO for user_key: %s", user_key)
        user_dto = UserDTO.find_by_user_key(user_key)
        if not user_dto or user_dto.account_key != account_key:
            logging.warning("User not found for user_key: %s, account_key: %s", user_key, account_key)
            return respond_error('User not found', status=404)
        if request.method == 'PUT':
            if 'admin' not in roles:
                logging.warning("Non-admin tried to update subscriptions")
                return respond_error('Only admin can update subscriptions', status=403)
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
        return respond_success({'user_key': user_key, 'account_key': account_key, 'subscription': resp_subscription})
    except Exception as e:
        logging.exception("Exception in /subscriptions endpoint")
        return respond_error('Server error', status=500)

@auth_bp.route('/account/<account_key>/company', methods=['GET'])
def get_company_name(account_key):
    # Find any admin user for this account_key
    admin_doc = user_repo.find_one({
        'account_key': account_key,
        'roles': {'$in': ['admin']}
    })
    if admin_doc and 'company_name' in admin_doc:
        return respond_success({'company_name': admin_doc['company_name']})
    return respond_error('Company not found', status=404)

# API blueprint for auth-level API compatibility
auth_api_bp = Blueprint('auth_api', __name__, url_prefix='/api')

@auth_api_bp.route('/auth/me', methods=['POST'])
def api_auth_me():
    try:
        payload = get_auth_payload(request)
        user = None
        try:
            from fin_server.repository.mongo_helper import get_collection
            user_repo = get_collection('users')
            user = user_repo.find_one({'user_key': payload.get('user_key'), 'account_key': payload.get('account_key')})
        except Exception:
            current_app.logger.exception('Error fetching user in api_auth_me')
        if not user:
            return respond_error('User not found', status=404)
        user_out = normalize_doc(user)
        user_out['_id'] = str(user_out.get('_id'))
        user_out['id'] = user_out.get('user_key') or user_out['_id']
        return respond_success({'user': user_out})
    except Exception:
        current_app.logger.exception('Error in api_auth_me')
        return respond_error('Server error', status=500)

@auth_api_bp.route('/auth/refresh', methods=['POST'])
def api_auth_refresh():
    try:
        data = request.get_json(force=True)
        refresh_token = data.get('refreshToken') or data.get('refresh_token') or data.get('token')
        if not refresh_token:
            return respond_error('Missing refreshToken', status=400)
        try:
            payload = AuthSecurity.decode_token(refresh_token)
            user_key = payload.get('user_key')
            from fin_server.repository.mongo_helper import get_collection
            user_repo = get_collection('users')
            user = user_repo.find_one({'user_key': user_key})
            if not user:
                return respond_error('User not found', status=404)
            valid = AuthSecurity.validate_refresh_token(user_repo, 'users', user_key, refresh_token)
            if not valid:
                return respond_error('Invalid or expired refresh token', status=401)
            access_token = AuthSecurity.encode_token({'user_key': user_key, 'account_key': user.get('account_key'), 'roles': user.get('roles', []), 'type': 'access'})
            return respond_success({'accessToken': access_token})
        except Exception:
            current_app.logger.exception('Refresh token validation failed')
            return respond_error('Invalid refresh token', status=401)
    except Exception:
        current_app.logger.exception('Error in api_auth_refresh')
        return respond_error('Server error', status=500)
