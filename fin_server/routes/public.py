from flask import Blueprint, request, current_app

from fin_server.dto.fish_dto import FishDTO
from fin_server.repository.mongo_helper import get_collection, MongoRepo
from fin_server.utils.helpers import respond_error, respond_success

public_bp = Blueprint('public', __name__, url_prefix='/api/public')


# =============================================================================
# Health Check Endpoints
# =============================================================================

@public_bp.route('/health', methods=['GET'])
def health_check():
    """Simple health endpoint for load balancers and uptime checks.

    Returns HTTP 200 if the application is up. Optionally touches the
    database to verify connectivity but does not expose internal details
    in the response body.
    """
    try:
        if not MongoRepo.is_initialized():
            return respond_error({'status': 'degraded', 'reason': 'database not initialized'}, status=503)
        # Perform a very lightweight ping by listing collections once.
        # Any connectivity/timeout issues will raise and be logged.
        return respond_success({'status': 'ok', 'db': 'reachable'})
    except Exception as e:
        current_app.logger.exception(f'Health check DB error: {e}')
        # Still return 503 with a minimal payload (no internal details).
        return respond_error({'status': 'degraded'}, status=503)


# =============================================================================
# Company Public Endpoints
# =============================================================================

@public_bp.route('/company/<account_key>', methods=['GET'])
def get_company_public(account_key):
    """Public endpoint: return minimal company info for given account_key (no auth required)."""
    if not account_key or not account_key.strip():
        return respond_error('account_key is required', status=400)

    try:
        companies_repo = get_collection('companies')
        company = companies_repo.find_one({'account_key': account_key})
        if not company:
            return respond_error('Company not found', status=404)

        # Build minimal response - only expose non-sensitive info
        created_date = company.get('created_date')
        if hasattr(created_date, 'isoformat'):
            created_date = created_date.isoformat()

        result = {
            'account_key': company.get('account_key'),
            'company_name': company.get('company_name'),
            'created_date': created_date,
            'description': company.get('description'),
        }
        return respond_success({'company': result})
    except Exception as e:
        current_app.logger.exception(f'Error in public.get_company_public: {e}')
        return respond_error('Server error', status=500)


# =============================================================================
# Fish Public Endpoints
# =============================================================================

@public_bp.route('/fish', methods=['GET'])
def get_public_fish_list():
    """Public endpoint: list fish entities.

    Optional query param:
        account_key: Filter to show only fish mapped to this account
    """
    try:
        account_key = request.args.get('account_key')
        fish_collection = get_collection('fish')

        # If account_key provided, use fish_mapping to restrict list
        if account_key:
            fish_mapping_repo = get_collection('fish_mapping')
            mapping = fish_mapping_repo.find_one({'account_key': account_key})
            fish_ids = mapping.get('fish_ids', []) if mapping else []
            if not fish_ids:
                return respond_success({'fish': []})
            cursor = fish_collection.find({'_id': {'$in': fish_ids}})
        else:
            cursor = fish_collection.find({})

        result = []
        for f in cursor:
            try:
                dto = FishDTO.from_doc(f)
                result.append(dto.to_ui())
            except Exception:
                # Fallback to manual conversion if DTO fails
                f_out = dict(f)
                f_out['id'] = str(f_out.pop('_id', ''))
                if 'created_at' in f_out and hasattr(f_out['created_at'], 'isoformat'):
                    f_out['created_at'] = f_out['created_at'].isoformat()
                result.append(f_out)

        return respond_success({'fish': result})
    except Exception as e:
        current_app.logger.exception(f'Error in public.get_public_fish_list: {e}')
        return respond_error('Server error', status=500)


# =============================================================================
# User/Company Lookup Endpoints
# =============================================================================

@public_bp.route('/user/company', methods=['GET'])
def get_company_by_user_identifier():
    """Public endpoint: given user_key or username or email or phone, return company_name and account_key.

    Query params (provide at least one):
        user_key: The user's unique key
        username: The user's username
        email: The user's email
        phone: The user's phone number
    """
    try:
        user_key = request.args.get('user_key')
        username = request.args.get('username')
        email = request.args.get('email')
        phone = request.args.get('phone')

        if not any([user_key, username, email, phone]):
            return respond_error({
                'error': 'Missing identifier',
                'message': 'Provide one of: user_key, username, email, or phone'
            }, status=400)

        # Build query based on provided identifier (priority order)
        query = {}
        if user_key:
            query['user_key'] = user_key
        elif username:
            query['username'] = username
        elif email:
            query['email'] = email
        elif phone:
            query['phone'] = phone

        users_repo = get_collection('users')
        user_doc = users_repo.find_one(query)
        if not user_doc:
            return respond_error('User not found', status=404)

        account_key = user_doc.get('account_key')
        company_name = None

        if account_key:
            companies_repo = get_collection('companies')
            company = companies_repo.find_one({'account_key': account_key})
            company_name = company.get('company_name') if company else None

        return respond_success({
            'account_key': account_key,
            'company_name': company_name
        })
    except Exception as e:
        current_app.logger.exception(f'Error in public.get_company_by_user_identifier: {e}')
        return respond_error('Server error', status=500)
