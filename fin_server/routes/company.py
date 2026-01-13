"""Company routes for company registration and management.

This module provides endpoints for:
- Company registration with admin user
- Company details retrieval and updates
- Public company info
"""
import logging

from flask import Blueprint, request

from config import config
from fin_server.dto.company_dto import CompanyDTO
from fin_server.repository.mongo_helper import get_collection
from fin_server.security.authentication import AuthSecurity
from fin_server.utils.decorators import handle_errors, require_auth
from fin_server.utils.generator import build_user, get_current_timestamp, epoch_to_datetime
from fin_server.utils.helpers import respond_success, respond_error

logger = logging.getLogger(__name__)


# Blueprint
company_bp = Blueprint('company', __name__, url_prefix='/company')

# Repositories
user_repo = get_collection('users')
companies_repo = get_collection('companies')


# =============================================================================
# Helper Functions
# =============================================================================

def _build_company_users_list(account_key):
    """Build list of company users with their status from user repository.

    Users are stored in the users collection with account_key reference,
    not embedded in the company document.
    """
    users = user_repo.find_many({'account_key': account_key})
    return [
        {
            'user_key': u.get('user_key'),
            'username': u.get('username'),
            'roles': u.get('roles', []),
            'joined_date': u.get('joined_date'),
            'active': bool(u.get('refresh_tokens'))
        }
        for u in users
    ]


def _get_active_employee_count(users_list):
    """Count active employees from users list."""
    return sum(1 for u in users_list if u.get('active'))


def _sync_company_employee_count(account_key):
    """Update the company's employee count based on users in users collection.

    Returns:
        tuple: (users_list, employee_count)
    """
    users_list = _build_company_users_list(account_key)
    employee_count = len(users_list)

    # Update only the employee_count field
    companies_repo.update_employee_count(account_key, absolute_count=employee_count)

    return users_list, employee_count


# Backward compatibility alias
_sync_company_users = _sync_company_employee_count



def _build_company_response(company, users_list=None, employee_count=None):
    """Build company response dict."""
    if company is None:
        return None

    response = dict(company)
    response.pop('_id', None)

    if users_list is not None:
        response['users'] = users_list
    if employee_count is not None:
        response['employee_count'] = employee_count

    return response


def _format_created_date(created_date_raw):
    """Format created date for response."""
    if isinstance(created_date_raw, (int, float)):
        try:
            return epoch_to_datetime(int(created_date_raw)).split(' ')[0]
        except Exception:
            pass
    return created_date_raw


def _build_owner_object(admin_user, admin_user_key):
    """Build owner object for public response."""
    if admin_user:
        return {
            'user_key': admin_user.get('user_key'),
            'username': admin_user.get('username')
        }
    return {
        'user_key': admin_user_key,
        'username': None
    }


# =============================================================================
# Company Registration
# =============================================================================

@company_bp.route('/register', methods=['POST'])
@handle_errors
def register_company():
    """Register a new company with admin user."""
    logger.info('POST /company/register called')
    data = request.get_json(force=True)

    # Validate master password using centralized config
    is_valid, error_msg = config.validate_master_password(data.get('master_password'))
    if not is_valid:
        logger.warning('Company registration failed: %s', error_msg)
        return respond_error(error_msg, status=403 if 'Invalid' in error_msg else 500)

    data.pop('master_password', None)

    # Validate required fields
    company_name = data.get('company_name')
    if not company_name or not str(company_name).strip():
        return respond_error('company_name is required', status=400)

    if not data.get('username') or not data.get('password'):
        return respond_error('username and password are required', status=400)

    if not (data.get('email') or data.get('phone')):
        return respond_error('Either email or phone is required', status=400)

    # Ensure admin role
    roles = data.get('roles') or ['admin']
    if 'admin' not in roles:
        roles.append('admin')
    data['roles'] = roles

    # Build admin user
    admin_data = build_user(data)
    user_id = user_repo.create(admin_data)

    logger.info('Admin user created with ID: %s', user_id)

    account_key = admin_data['account_key']
    admin_user_key = admin_data['user_key']
    created_ts = get_current_timestamp()

    # Create company document using repository
    # Note: Users are tracked via account_key in users collection, not embedded here
    company_doc = {
        'account_key': account_key,
        'company_name': company_name,
        'admin_user_key': admin_user_key,
        'created_date': created_ts,
        'pincode': data.get('pincode'),
        'description': data.get('description'),
        'employee_count': 1
    }

    # Use repository create method (with duplicate check)
    try:
        companies_repo.create(company_doc)
    except ValueError as ve:
        # Company already exists
        logger.warning('Company creation failed: %s', ve)
        return respond_error(str(ve), status=409)

    # Issue tokens
    access_token = AuthSecurity.encode_token({
        'user_key': admin_user_key,
        'account_key': account_key,
        'roles': admin_data.get('roles', []),
        'type': 'access'
    })
    refresh_token = admin_data.get('refresh_tokens', [None])[0]

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

    logger.info('Company registered: %s', account_key)
    return respond_success(response, status=201)


# =============================================================================
# Company Details
# =============================================================================

@company_bp.route('/<account_key>', methods=['GET'])
@handle_errors
@require_auth
def get_company(account_key, auth_payload):
    """Get company details (requires authenticated user of account)."""
    logger.debug('GET /company/%s called', account_key)

    if auth_payload.get('account_key') != account_key:
        return respond_error('Unauthorized', status=403)

    # Use repository method
    company = companies_repo.get_by_account_key(account_key)
    if not company:
        return respond_error('Company not found', status=404)

    # Sync and get current users list
    users_list, employee_count = _sync_company_users(account_key)

    return respond_success({
        'company': _build_company_response(company, users_list, employee_count)
    })


@company_bp.route('/<account_key>', methods=['PUT'])
@handle_errors
@require_auth
def update_company(account_key, auth_payload):
    """Update company details (only original admin)."""
    logger.debug('PUT /company/%s called', account_key)

    # Check authorization
    if auth_payload.get('account_key') != account_key:
        return respond_error('Unauthorized', status=403)

    if 'admin' not in auth_payload.get('roles', []):
        return respond_error('Unauthorized', status=403)

    # Use repository method
    company = companies_repo.get_by_account_key(account_key)
    if not company:
        return respond_error('Company not found', status=404)

    # Only original admin can update
    if auth_payload.get('user_key') != company.get('admin_user_key'):
        return respond_error('Only the original admin can update company details', status=403)

    data = request.get_json(force=True)

    # Build update fields
    update_fields = {
        field: data[field]
        for field in ['company_name', 'pincode', 'description']
        if field in data and data[field] is not None
    }

    if update_fields:
        # Update company using repository
        companies_repo.update({'account_key': account_key}, update_fields)

        # Propagate company_name to user docs if changed
        if 'company_name' in update_fields:
            companies_repo.update_company_name(account_key, update_fields['company_name'])
            user_repo.update(
                {'account_key': account_key},
                {'company_name': update_fields['company_name']},
                multi=True
            )

    # Sync users list
    users_list, employee_count = _sync_company_users(account_key)

    updated_company = companies_repo.get_by_account_key(account_key)
    return respond_success({
        'company': _build_company_response(updated_company, users_list, employee_count)
    })


# =============================================================================
# Public Endpoints
# =============================================================================

@company_bp.route('/public/<account_key>', methods=['GET'])
@handle_errors
def get_company_public(account_key):
    """Get minimal company info (no auth required)."""
    logger.debug('GET /company/public/%s called', account_key)

    # Use repository method
    company = companies_repo.get_by_account_key(account_key)
    if not company:
        return respond_error('Company not found', status=404)

    # Get admin user info
    admin_user_key = company.get('admin_user_key')
    admin_user = user_repo.find_one({'user_key': admin_user_key}) if admin_user_key else None

    # Count active workers
    users = user_repo.find_many({'account_key': account_key})
    worker_count = sum(1 for u in users if u.get('refresh_tokens'))

    # Format created date
    created_date_fmt = _format_created_date(company.get('created_date'))

    # Build owner object
    owner_obj = _build_owner_object(admin_user, admin_user_key)

    # Try to use DTO
    try:
        cdto = CompanyDTO.from_doc(company)
        cdict = cdto.to_dict()
        cdict['owner'] = owner_obj
        cdict['worker_count'] = worker_count
        return respond_success({'company': cdict})
    except Exception:
        return respond_success({
            'company': {
                'account_key': company.get('account_key'),
                'company_name': company.get('company_name'),
                'created_date': created_date_fmt,
                'owner': owner_obj,
                'worker_count': worker_count
            }
        })


# =============================================================================
# Company User Management Endpoints
# =============================================================================

@company_bp.route('/<account_key>/users', methods=['GET'])
@handle_errors
@require_auth
def get_company_users(account_key, auth_payload):
    """Get list of users in a company."""
    logger.debug('GET /company/%s/users called', account_key)

    if auth_payload.get('account_key') != account_key:
        return respond_error('Unauthorized', status=403)

    # Sync users and return
    users_list, employee_count = _sync_company_users(account_key)

    return respond_success({
        'users': users_list,
        'employee_count': employee_count
    })


@company_bp.route('/<account_key>/users/<user_key>', methods=['DELETE'])
@handle_errors
@require_auth
def remove_company_user(account_key, user_key, auth_payload):
    """Remove a user from company (admin only)."""
    logger.debug('DELETE /company/%s/users/%s called', account_key, user_key)

    if auth_payload.get('account_key') != account_key:
        return respond_error('Unauthorized', status=403)

    if 'admin' not in auth_payload.get('roles', []):
        return respond_error('Only admin can remove users', status=403)

    # Cannot remove self
    if auth_payload.get('user_key') == user_key:
        return respond_error('Cannot remove yourself', status=400)

    # Use repository method
    result = companies_repo.remove_user_from_company(account_key, user_key)

    if result.modified_count > 0:
        return respond_success({'message': 'User removed from company'})
    return respond_error('User not found in company', status=404)
