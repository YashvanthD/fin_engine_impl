import logging
from flask import Blueprint, request, jsonify
from fin_server.repository.user_repository import mongo_db_repository
from fin_server.security.authentication import AuthSecurity
from fin_server.utils.generator import build_user, get_current_timestamp, epoch_to_datetime
from fin_server.dto.user_dto import UserDTO
import datetime
import time
import os
import hmac

MASTER_ADMIN_PASSWORD = os.getenv('MASTER_ADMIN_PASSWORD')  # Must be set in environment

company_bp = Blueprint('company', __name__, url_prefix='/company')

# Helper to build company users list from user collection

def build_company_users_list(account_key):
    users = mongo_db_repository.find_many('users', {'account_key': account_key})
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
    data = request.get_json(force=True)
    # Master password verification
    provided_master = data.get('master_password')
    if MASTER_ADMIN_PASSWORD is None:
        logging.error('MASTER_ADMIN_PASSWORD not configured')
        return jsonify({'success': False, 'error': 'Server not configured for company registration'}), 500
    if not provided_master or not hmac.compare_digest(str(provided_master), str(MASTER_ADMIN_PASSWORD)):
        logging.warning('Invalid master password for company registration')
        return jsonify({'success': False, 'error': 'Unauthorized: invalid master password'}), 403
    data.pop('master_password', None)
    company_name = data.get('company_name')
    if not company_name or not str(company_name).strip():
        return jsonify({'success': False, 'error': 'company_name is required'}), 400
    # Admin user required fields
    if not data.get('username') or not data.get('password'):
        return jsonify({'success': False, 'error': 'username and password are required'}), 400
    if not (data.get('email') or data.get('phone')):
        return jsonify({'success': False, 'error': 'Either email or phone is required'}), 400
    # Ensure roles contains admin
    roles = data.get('roles')
    if not roles:
        roles = ['admin']
    elif 'admin' not in roles:
        roles.append('admin')
    data['roles'] = roles
    # Pass company_name into build_user; build_user enforces company_name for admin
    try:
        admin_data = build_user(data)
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    # Insert admin user
    try:
        user_id = mongo_db_repository.create('users', admin_data)
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    account_key = admin_data['account_key']
    admin_user_key = admin_data['user_key']
    # Create company doc
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
    mongo_db_repository.get_collection('companies').insert_one(company_doc)
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
        'success': True,
        'message': 'Company registered',
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
    return jsonify(response), 201

# Get company details (requires any authenticated user of account)
@company_bp.route('/<account_key>', methods=['GET'])
def get_company(account_key):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        if payload.get('account_key') != account_key:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        company = mongo_db_repository.find_one('companies', {'account_key': account_key})
        if not company:
            return jsonify({'success': False, 'error': 'Company not found'}), 404
        company.pop('_id', None)
        # Rebuild users list to ensure it is current
        users_list = build_company_users_list(account_key)
        employee_count = sum(1 for u in users_list if u.get('active'))
        mongo_db_repository.update('companies', {'account_key': account_key}, {
            'users': users_list,
            'employee_count': employee_count
        })
        company['users'] = users_list
        company['employee_count'] = employee_count
        return jsonify({'success': True, 'company': company}), 200
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 401
    except Exception:
        logging.exception('Error in get_company')
        return jsonify({'success': False, 'error': 'Server error'}), 500

# Update company details (name, pincode, description) - ONLY original admin of account
@company_bp.route('/<account_key>', methods=['PUT'])
def update_company(account_key):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        roles = payload.get('roles', [])
        user_key = payload.get('user_key')
        if payload.get('account_key') != account_key or 'admin' not in roles:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        company = mongo_db_repository.find_one('companies', {'account_key': account_key})
        if not company:
            return jsonify({'success': False, 'error': 'Company not found'}), 404
        admin_user_key = company.get('admin_user_key')
        if user_key != admin_user_key:
            return jsonify({'success': False, 'error': 'Only the original admin can update company details'}), 403
        data = request.get_json(force=True)
        update_fields = {}
        for field in ['company_name', 'pincode', 'description']:
            if field in data and data[field] is not None:
                update_fields[field] = data[field]
        if update_fields:
            mongo_db_repository.update('companies', {'account_key': account_key}, update_fields)
            # If company_name changed, propagate to user docs
            if 'company_name' in update_fields:
                mongo_db_repository.update('users', {'account_key': account_key}, {'company_name': update_fields['company_name']})
        # Rebuild users list and employee count
        users_list = build_company_users_list(account_key)
        employee_count = sum(1 for u in users_list if u.get('active'))
        mongo_db_repository.update('companies', {'account_key': account_key}, {
            'users': users_list,
            'employee_count': employee_count
        })
        updated_company = mongo_db_repository.find_one('companies', {'account_key': account_key})
        updated_company.pop('_id', None)
        updated_company['users'] = users_list
        updated_company['employee_count'] = employee_count
        return jsonify({'success': True, 'company': updated_company}), 200
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 401
    except Exception:
        logging.exception('Error in update_company')
        return jsonify({'success': False, 'error': 'Server error'}), 500

# Public: minimal company info (no auth) -> company_name, created_date, owner, worker_count, account_key
@company_bp.route('/public/<account_key>', methods=['GET'])
def get_company_public(account_key):
    try:
        company = mongo_db_repository.find_one('companies', {'account_key': account_key})
        if not company:
            return jsonify({'success': False, 'error': 'Company not found'}), 404
        admin_user_key = company.get('admin_user_key')
        admin_user = None
        if admin_user_key:
            admin_user = mongo_db_repository.find_one('users', {'user_key': admin_user_key})
        # Recompute active workers count (do not persist/mutate company doc)
        users = mongo_db_repository.find_many('users', {'account_key': account_key})
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
        return jsonify({
            'success': True,
            'company': {
                'account_key': company.get('account_key'),
                'company_name': company.get('company_name'),
                'created_date': created_date_fmt or created_date_raw,
                'owner': owner_obj,
                'worker_count': worker_count
            }
        }), 200
    except Exception:
        logging.exception('Error in get_company_public')
        return jsonify({'success': False, 'error': 'Server error'}), 500
