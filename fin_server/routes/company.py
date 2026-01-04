import logging
from flask import Blueprint, request, current_app
from fin_server.utils.helpers import respond_success, respond_error

from fin_server.security.authentication import AuthSecurity
from fin_server.utils.generator import build_user, get_current_timestamp, epoch_to_datetime
from fin_server.repository.mongo_helper import get_collection
from fin_server.dto.company_dto import CompanyDTO

user_repo = get_collection('users')

import os
import hmac

MASTER_ADMIN_PASSWORD = os.getenv('MASTER_ADMIN_PASSWORD', 'password')  # Must be set in environment

company_bp = Blueprint('company', __name__, url_prefix='/company')

# Helper to build company users list from user collection

def build_company_users_list(account_key):
    # user_repo.find_many expects a query dict (collection is implied by repository)
    users = user_repo.find_many({'account_key': account_key})
    result = []
    for u in users:
        user_entry = {
            'user_key': u.get('user_key'),
            'username': u.get('username'),
            'roles': u.get('roles', []),
            'joined_date': u.get('joined_date'),
            # Active if at least one refresh token exists
            'active': bool(u.get('refresh_tokens'))
        }
        result.append(user_entry)
    return result

# Register a new company and its admin user
@company_bp.route('/register', methods=['POST'])
def register_company():
    current_app.logger.debug('POST /api/v1/company/register called with data: %s', request.json)
    current_app.logger.info('POST /company/register called')
    data = request.get_json(force=True)
    # Master password verification
    provided_master = data.get('master_password')
    if MASTER_ADMIN_PASSWORD is None:
        logging.error('MASTER_ADMIN_PASSWORD not configured')
        return respond_error('Server not configured for company registration', status=500)
    if not provided_master or not hmac.compare_digest(str(provided_master), str(MASTER_ADMIN_PASSWORD) and not(provided_master == MASTER_ADMIN_PASSWORD)):
        logging.warning('Invalid master password for company registration')
        return respond_error('Unauthorized: invalid master password', status=403)
    data.pop('master_password', None)
    company_name = data.get('company_name')
    if not company_name or not str(company_name).strip():
        return respond_error('company_name is required', status=400)
    # Admin user required fields
    if not data.get('username') or not data.get('password'):
        return respond_error('username and password are required', status=400)
    if not (data.get('email') or data.get('phone')):
        return respond_error('Either email or phone is required', status=400)
    # Ensure roles contains admin
    roles = data.get('roles')
    if not roles:
        roles = ['admin']
    elif 'admin' not in roles:
        roles.append('admin')
    data['roles'] = roles
    current_app.logger.info(f'Received company registration data: {data}')
    # Pass company_name into build_user; build_user enforces company_name for admin
    try:
        admin_data = build_user(data)
    except ValueError as ve:
        return respond_error(str(ve), status=400)
    # Insert admin user
    try:
        user_id = user_repo.create(admin_data)
    except ValueError as ve:
        return respond_error(str(ve), status=400)
    current_app.logger.info(f'Admin user created with ID: {user_id}')
    account_key = admin_data['account_key']
    admin_user_key = admin_data['user_key']
    # Create company doc
    # created_ts is epoch seconds; UI helpers convert to IST when displaying
    created_ts = get_current_timestamp()
    company_doc = {
        'account_key': account_key,
        'company_name': company_name,
        'admin_user_key': admin_user_key,
        'users': [
            {
                'user_key': admin_user_key,
                'username': admin_data.get('username'),
                'roles': admin_data.get('roles', []),
                'joined_date': admin_data.get('joined_date'),
                'active': True
            }
        ],
        'created_date': created_ts,
        'pincode': data.get('pincode'),
        'description': data.get('description'),
        'employee_count': 1
    }
    user_repo.get_collection('companies').insert_one(company_doc)
    current_app.logger.info(f'Company document: {company_doc}')
    # Issue access token for admin
    access_payload = {
        'user_key': admin_user_key,
        'account_key': account_key,
        'roles': admin_data.get('roles', []),
        'type': 'access'
    }
    access_token = AuthSecurity.encode_token(access_payload)
    refresh_token = admin_data['refresh_tokens'][0] if admin_data.get('refresh_tokens') else None
    response = {
        'company': {
            'account_key': account_key,
            'company_name': company_name,
            'created_date': created_ts,
            'pincode': company_doc.get('pincode'),
            'description': company_doc.get('description'),
            'employee_count': company_doc.get('employee_count')
        },
        'admin': {
            'user_key': admin_user_key,
            'username': admin_data.get('username'),
            'roles': admin_data.get('roles', [])
        },
        'access_token': access_token,
        'refresh_token': refresh_token
    }
    current_app.logger.info(f'Company registered: {response}')
    return respond_success(response, status=201)

# Get company details (requires any authenticated user of account)
@company_bp.route('/<account_key>', methods=['GET'])
def get_company(account_key):
    current_app.logger.debug('GET /api/v1/company/%s called', account_key)
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return respond_error('Missing or invalid token', status=401)
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        if payload.get('account_key') != account_key:
            return respond_error('Unauthorized', status=403)
        # Companies are stored in a separate collection; use helper to access it
        coll = get_collection('companies')
        company = coll.find_one({'account_key': account_key})
        if not company:
            return respond_error('Company not found', status=404)
        company.pop('_id', None)
        # Rebuild users list to ensure it is current
        users_list = build_company_users_list(account_key)
        employee_count = sum(1 for u in users_list if u.get('active'))
        # Persist updated company users/employee_count
        coll.update_one({'account_key': account_key}, {'$set': {'users': users_list, 'employee_count': employee_count}}, upsert=False)
        company['users'] = users_list
        company['employee_count'] = employee_count
        return respond_success({'company': company})
    except ValueError as ve:
        return respond_error(str(ve), status=401)
    except Exception:
        logging.exception('Error in get_company')
        return respond_error('Server error', status=500)

# Update company details (name, pincode, description) - ONLY original admin of account
@company_bp.route('/<account_key>', methods=['PUT'])
def update_company(account_key):
    current_app.logger.debug('PUT /api/v1/company/%s called with data: %s', account_key, request.json)
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return respond_error('Missing or invalid token', status=401)
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        roles = payload.get('roles', [])
        user_key = payload.get('user_key')
        if payload.get('account_key') != account_key or 'admin' not in roles:
            return respond_error('Unauthorized', status=403)
        coll = get_collection('companies')
        company = coll.find_one({'account_key': account_key})
        if not company:
            return respond_error('Company not found', status=404)
        admin_user_key = company.get('admin_user_key')
        if user_key != admin_user_key:
            return respond_error('Only the original admin can update company details', status=403)
        data = request.get_json(force=True)
        update_fields = {}
        for field in ['company_name', 'pincode', 'description']:
            if field in data and data[field] is not None:
                update_fields[field] = data[field]
        if update_fields:
            # Persist updates to companies collection
            coll.update_one({'account_key': account_key}, {'$set': update_fields}, upsert=False)
            # If company_name changed, propagate to user docs (multi update)
            if 'company_name' in update_fields:
                user_repo.update({'account_key': account_key}, {'company_name': update_fields['company_name']}, multi=True)
        # Rebuild users list and employee count
        users_list = build_company_users_list(account_key)
        employee_count = sum(1 for u in users_list if u.get('active'))
        # Persist users list and employee count to companies collection
        coll.update_one({'account_key': account_key}, {'$set': {'users': users_list, 'employee_count': employee_count}}, upsert=False)
        updated_company = coll.find_one({'account_key': account_key})
        updated_company.pop('_id', None)
        updated_company['users'] = users_list
        updated_company['employee_count'] = employee_count
        return respond_success({'company': updated_company})
    except ValueError as ve:
        return respond_error(str(ve), status=401)
    except Exception:
        logging.exception('Error in update_company')
        return respond_error('Server error', status=500)

# Public: minimal company info (no auth) -> company_name, created_date, owner, worker_count, account_key
@company_bp.route('/public/<account_key>', methods=['GET'])
def get_company_public(account_key):
    current_app.logger.debug('GET /api/v1/company/public/%s called', account_key)
    try:
        # Use companies collection for company lookup
        coll = get_collection('companies')
        company = coll.find_one({'account_key': account_key})
        if not company:
            return respond_error('Company not found', status=404)
        admin_user_key = company.get('admin_user_key')
        admin_user = None
        if admin_user_key:
            admin_user = user_repo.find_one({'user_key': admin_user_key})
        # Recompute active workers count (do not persist/mutate company doc)
        users = user_repo.find_many({'account_key': account_key})
        worker_count = 0
        for u in users:
            if u.get('refresh_tokens'):
                worker_count += 1
        created_date_raw = company.get('created_date')
        # Convert epoch (int) to YYYY-MM-DD if possible
        created_date_fmt = None
        if isinstance(created_date_raw, (int, float)):
            try:
                created_date_fmt = epoch_to_datetime(int(created_date_raw)).split(' ')[0]
            except Exception:
                created_date_fmt = created_date_raw
        owner_obj = None
        if admin_user:
            owner_obj = {
                'user_key': admin_user.get('user_key'),
                'username': admin_user.get('username')
            }
        else:
            owner_obj = {'user_key': admin_user_key, 'username': None}
        # Build DTO for response
        try:
            cdto = CompanyDTO.from_doc(company)
            cdict = cdto.to_dict()
            cdict['owner'] = owner_obj
            cdict['worker_count'] = worker_count
            return respond_success({'company': cdict})
        except Exception:
            return respond_success({'company': {
                'account_key': company.get('account_key'),
                'company_name': company.get('company_name'),
                'created_date': created_date_fmt or created_date_raw,
                'owner': owner_obj,
                'worker_count': worker_count
            }})
    except Exception:
        logging.exception('Error in get_company_public')
        return respond_error('Server error', status=500)
