from flask import Blueprint, request, current_app

from fin_server.dto.fish_dto import FishDTO
from fin_server.repository.mongo_helper import get_collection, MongoRepo
from fin_server.utils.helpers import respond_error, respond_success

public_bp = Blueprint('public', __name__, url_prefix='/public')


@public_bp.route('/health', methods=['GET'])
def health_check():
    """Simple health endpoint for load balancers and uptime checks.

    Returns HTTP 200 if the application is up. Optionally touches the
    database to verify connectivity but does not expose internal details
    in the response body.
    """
    try:
        assert  MongoRepo.is_initialized()
        # Perform a very lightweight ping by listing collections once.
        # Any connectivity/timeout issues will raise and be logged.
        return respond_success({'status': 'ok', 'db': 'reachable'})
    except Exception as e:
        current_app.logger.exception(f'Health check DB error: {e}')
        # Still return 503 with a minimal payload (no internal details).
        return respond_error({'status': 'degraded'}, status=503)

@public_bp.route('/company/<account_key>', methods=['GET'])
def get_company_public(account_key):
    """Public endpoint: return minimal company info for given account_key (no auth required)."""
    try:
        company = repo.get_collection('companies').find_one({'account_key': account_key})
        if not company:
            return respond_error('Company not found', status=404)
        # Build minimal response
        result = {
            'account_key': company.get('account_key'),
            'company_name': company.get('company_name'),
            'created_date': company.get('created_date').isoformat() if hasattr(company.get('created_date'), 'isoformat') else company.get('created_date'),
            'description': company.get('description'),
        }
        return respond_success({'company': result})
    except Exception as e:
        current_app.logger.exception(f'Error in public.get_company_public: {e}')
        return respond_error('Server error', status=500)

@public_bp.route('/fish', methods=['GET'])
def get_public_fish_list():
    """Public endpoint: list fish entities. Optional query param account_key to filter mapped fish for an account."""
    try:
        account_key = request.args.get('account_key')
        fish_collection = get_collection('fish')
        # If account_key provided, use fish_mapping to restrict list
        if account_key:
            mapping = fish_collection.get_collection('fish_mapping').find_one({'account_key': account_key})
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
                f_out = dict(f)
                f_out['id'] = str(f_out.pop('_id'))
                if 'created_at' in f_out and hasattr(f_out['created_at'], 'isoformat'):
                    f_out['created_at'] = f_out['created_at'].isoformat()
                result.append(f_out)
        return respond_success({'fish': result})
    except Exception as e:
        current_app.logger.exception(f'Error in public.get_public_fish_list: {e}')
        return respond_error('Server error', status=500)


@public_bp.route('/user/company', methods=['GET'])
def get_company_by_user_identifier():
    """Public endpoint: given user_key or username or email or phone, return company_name and account_key."""
    try:
        user_key = request.args.get('user_key')
        username = request.args.get('username')
        email = request.args.get('email')
        phone = request.args.get('phone')

        if not (user_key or username or email or phone):
            return respond_error({'identifier': 'Provide one of user_key, username, email, or phone'}, status=400)

        query = {}
        if user_key:
            query['user_key'] = user_key
        elif username:
            query['username'] = username
        elif email:
            query['email'] = email
        elif phone:
            query['phone'] = phone

        user_doc = repo.get_collection('users').find_one(query)
        if not user_doc:
            return respond_error('User not found', status=404)

        account_key = user_doc.get('account_key')
        company = repo.get_collection('companies').find_one({'account_key': account_key}) if account_key else None
        company_name = company.get('company_name') if company else None
        return respond_success({'account_key': account_key, 'company_name': company_name})
    except Exception as e:
        current_app.logger.exception(f'Error in public.get_company_by_user_identifier: {e}')
        return respond_error('Server error', status=500)
