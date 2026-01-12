"""Feeding routes for fish feeding records.

This module provides endpoints for:
- Feeding record creation
- Feeding record listing
- Feeding records by pond
"""
import logging

from flask import Blueprint, request

from fin_server.dto.feeding_dto import FeedingRecordDTO
from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.decorators import handle_errors, require_auth
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc

logger = logging.getLogger(__name__)

# Blueprint
feeding_bp = Blueprint('feeding', __name__, url_prefix='/feeding')

# Repository
feeding_repo = get_collection('feeding')


# =============================================================================
# Helper Functions
# =============================================================================

def _normalize_feeding_doc(doc):
    """Normalize feeding document to DTO format."""
    normalized = normalize_doc(doc)
    try:
        dto = FeedingRecordDTO.from_doc(normalized)
        return dto.to_dict()
    except Exception:
        normalized['_id'] = str(normalized.get('_id'))
        normalized['id'] = normalized.get('_id')
        return normalized


def _get_feeding_list(query):
    """Get list of feeding records matching query."""
    try:
        feeds = feeding_repo.find(query)
    except Exception:
        feeds = list(feeding_repo.find(query).sort('created_at', -1))

    return [_normalize_feeding_doc(f) for f in feeds]


# =============================================================================
# Feeding Endpoints
# =============================================================================

# Get expenses repo for feed cost tracking
expenses_repo = get_collection('expenses')


def create_feeding_expense(account_key, pond_id, feed_type, quantity, cost, user_key, feeding_id=None):
    """Create an expense record for feed purchase/usage."""
    try:
        if not cost or float(cost) <= 0:
            return None

        from fin_server.utils.time_utils import get_time_date_dt
        expense_doc = {
            'account_key': account_key,
            'amount': float(cost),
            'currency': 'INR',
            'category': 'Operational',
            'subcategory': 'Feeding',
            'detail': feed_type or 'Feed',
            'category_path': f'Operational/Feeding/{feed_type or "Feed"}',
            'type': 'feed',
            'action': 'buy',
            'status': 'SUCCESS',
            'payment_method': 'cash',
            'recorded_by': user_key,
            'user_key': user_key,
            'notes': f'Feed: {quantity}kg of {feed_type}',
            'metadata': {
                'pond_id': pond_id,
                'feed_type': feed_type,
                'quantity_kg': quantity,
                'feeding_id': str(feeding_id) if feeding_id else None
            },
            'created_at': get_time_date_dt(include_time=True)
        }

        from fin_server.services.expense_service import create_expense_with_repo
        expense_id = create_expense_with_repo(expense_doc, expenses_repo)
        logger.info(f'Created feed expense {expense_id} for pond={pond_id}, amount={cost}')
        return expense_id
    except Exception:
        logger.exception('Failed to create feeding expense')
        return None


@feeding_bp.route('/', methods=['POST'])
@handle_errors
@require_auth
def create_feeding_route(auth_payload):
    """Create a new feeding record."""
    data = request.get_json(force=True)

    # Build DTO
    dto = FeedingRecordDTO.from_request(data)
    dto.recordedBy = auth_payload.get('user_key')
    dto.user_key = auth_payload.get('user_key')  # Who performed the action
    dto.account_key = auth_payload.get('account_key')  # Which organization

    # Persist
    try:
        res = dto.save(repo=feeding_repo)
        inserted_id = getattr(res, 'inserted_id', res)
        inserted_id = str(inserted_id) if inserted_id is not None else None
    except Exception:
        r = feeding_repo.insert_one(dto.to_db_doc())
        inserted_id = str(r.inserted_id)

    dto.id = inserted_id

    # Create expense if cost is provided
    expense_id = None
    feed_cost = data.get('cost') or data.get('feed_cost') or data.get('feedCost')
    if feed_cost:
        expense_id = create_feeding_expense(
            account_key=auth_payload.get('account_key'),
            pond_id=dto.pondId,
            feed_type=dto.feedType,
            quantity=dto.quantity,
            cost=feed_cost,
            user_key=auth_payload.get('user_key'),
            feeding_id=inserted_id
        )

    response = dto.to_dict()
    if expense_id:
        response['expenseId'] = str(expense_id)

    return respond_success(response, status=201)


@feeding_bp.route('/', methods=['GET'])
@handle_errors
@require_auth
def list_feeding_route(auth_payload):
    """List all feeding records."""
    q = {}

    # Filter by account_key for data isolation
    account_key = auth_payload.get('account_key')
    if account_key:
        q['account_key'] = account_key

    pond_id = request.args.get('pondId') or request.args.get('pond_id')
    if pond_id:
        q['pond_id'] = pond_id

    feeds = _get_feeding_list(q)
    return respond_success(feeds)


@feeding_bp.route('/pond/<pond_id>', methods=['GET'])
@handle_errors
def feeding_by_pond_route(pond_id):
    """Get feeding records for a specific pond."""
    feeds = list(feeding_repo.find({'pondId': pond_id}).sort('created_at', -1))
    out = [_normalize_feeding_doc(f) for f in feeds]
    return respond_success(out)


# =============================================================================
# API Blueprint Aliases
# =============================================================================

feeding_api_bp = Blueprint('feeding_api', __name__, url_prefix='/api')

@feeding_api_bp.route('/feeding', methods=['POST'])
@handle_errors
@require_auth
def api_create_feeding(auth_payload):
    return create_feeding_route(auth_payload)

@feeding_api_bp.route('/feeding', methods=['GET'])
@handle_errors
@require_auth
def api_list_feeding(auth_payload):
    return list_feeding_route(auth_payload)

@feeding_api_bp.route('/feeding/pond/<pond_id>', methods=['GET'])
@handle_errors
def api_feeding_by_pond(pond_id):
    return feeding_by_pond_route(pond_id)
