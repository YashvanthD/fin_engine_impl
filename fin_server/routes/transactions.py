"""Transaction routes for financial transactions.

This module provides endpoints for:
- Transaction CRUD operations
- Transaction listing with filters
"""
import logging

from bson import ObjectId
from flask import Blueprint, request, current_app

from fin_server.repository.mongo_helper import get_collection
from fin_server.services.expense_service import post_transaction_effects
from fin_server.utils.decorators import handle_errors, require_auth
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc, parse_iso_or_epoch

logger = logging.getLogger(__name__)

# Blueprint
transactions_bp = Blueprint('transactions', __name__, url_prefix='/transactions')

# Repository
transactions_repo = get_collection('transactions')


# =============================================================================
# Helper Functions
# =============================================================================

def _build_transaction_query(args, account_key):
    """Build MongoDB query from request args."""
    q = {}

    if account_key:
        q['account_key'] = account_key

    # Pond filter
    pond = args.get('pondId') or args.get('pond_id') or args.get('pond')
    if pond:
        q['pond_id'] = pond

    # Species filter
    species = args.get('species')
    if species:
        q['species'] = species

    # Type filter
    tx_type = args.get('type') or args.get('tx_type')
    if tx_type:
        q['type'] = tx_type

    # Date range
    start_raw = args.get('startDate') or args.get('start_date') or args.get('from')
    end_raw = args.get('endDate') or args.get('end_date') or args.get('to')

    start_dt = parse_iso_or_epoch(start_raw)
    end_dt = parse_iso_or_epoch(end_raw)

    if start_dt or end_dt:
        date_q = {}
        if start_dt:
            date_q['$gte'] = start_dt
        if end_dt:
            date_q['$lte'] = end_dt
        q['created_at'] = date_q

    return q


def _get_transaction_query(tx_id):
    """Get query dict for finding transaction by ID."""
    try:
        return {'_id': ObjectId(tx_id)}
    except Exception:
        return {'transaction_id': tx_id}


def _validate_transaction_access(doc, account_key):
    """Check if user has access to transaction."""
    if account_key and doc.get('account_key') and doc.get('account_key') != account_key:
        return False
    return True


# =============================================================================
# Transaction Endpoints
# =============================================================================

@transactions_bp.route('', methods=['OPTIONS'])
def transactions_options_root():
    """Handle OPTIONS request."""
    return current_app.make_default_options_response()


@transactions_bp.route('', methods=['GET'])
@handle_errors
@require_auth
def list_transactions(auth_payload):
    """List transactions with filters."""
    args = request.args.to_dict()

    # Parse limit
    try:
        limit = int(args.get('limit', 50))
        limit = max(1, limit)
    except ValueError:
        limit = 50

    q = _build_transaction_query(args, auth_payload.get('account_key'))

    cursor = transactions_repo.find(q).sort([('created_at', -1)]).limit(limit)
    out = [normalize_doc(r) for r in cursor]

    return respond_success(out)


@transactions_bp.route('', methods=['POST'])
@handle_errors
@require_auth
def create_transaction(auth_payload):
    """Create a new transaction."""
    data = request.get_json(force=True)

    data['recorded_by'] = data.get('recorded_by') or auth_payload.get('user_key')
    data['account_key'] = data.get('account_key') or auth_payload.get('account_key')

    res = transactions_repo.create_transaction(data)

    # Normalize return type
    tx_id = res.get('inserted_id') or res.get('_id') or res.get('id') if isinstance(res, dict) else res

    # Post transaction effects (best effort)
    if tx_id:
        try:
            post_transaction_effects(tx_id)
        except Exception:
            logger.exception('Failed to post transaction effects for %s', tx_id)

    # Fetch and return created doc
    doc = None
    if tx_id:
        try:
            doc = transactions_repo.find_one({'_id': tx_id})
        except Exception:
            coll = getattr(transactions_repo, 'collection', transactions_repo)
            doc = coll.find_one({'_id': tx_id})

    return respond_success(normalize_doc(doc) if doc else None, status=201)


@transactions_bp.route('/<tx_id>', methods=['GET'])
@handle_errors
@require_auth
def get_transaction(tx_id, auth_payload):
    """Get a transaction by ID."""
    query = _get_transaction_query(tx_id)
    doc = transactions_repo.find_one(query)

    if not doc:
        return respond_error('Transaction not found', status=404)

    if not _validate_transaction_access(doc, auth_payload.get('account_key')):
        return respond_error('Not authorized', status=403)

    return respond_success(normalize_doc(doc))


@transactions_bp.route('/<tx_id>', methods=['PUT'])
@handle_errors
@require_auth
def update_transaction(tx_id, auth_payload):
    """Update a transaction."""
    data = request.get_json(force=True)
    query = _get_transaction_query(tx_id)

    existing = transactions_repo.find_one(query)
    if not existing:
        return respond_error('Transaction not found', status=404)

    if not _validate_transaction_access(existing, auth_payload.get('account_key')):
        return respond_error('Not authorized', status=403)

    transactions_repo.update_one({'_id': existing.get('_id')}, {'$set': data})
    updated = transactions_repo.find_one({'_id': existing.get('_id')})

    return respond_success(normalize_doc(updated))


@transactions_bp.route('/<tx_id>', methods=['DELETE'])
@handle_errors
@require_auth
def delete_transaction(tx_id, auth_payload):
    """Delete a transaction."""
    query = _get_transaction_query(tx_id)

    existing = transactions_repo.find_one(query)
    if not existing:
        return respond_error('Transaction not found', status=404)

    if not _validate_transaction_access(existing, auth_payload.get('account_key')):
        return respond_error('Not authorized', status=403)

    transactions_repo.delete_one({'_id': existing.get('_id')})
    return respond_success({'deleted': True})


# =============================================================================
# API Blueprint Aliases
# =============================================================================

transactions_api_bp = Blueprint('transactions_api', __name__, url_prefix='/api')

@transactions_api_bp.route('/transactions', methods=['GET'])
@handle_errors
@require_auth
def api_list_transactions(auth_payload):
    return list_transactions(auth_payload)

@transactions_api_bp.route('/transactions', methods=['POST'])
@handle_errors
@require_auth
def api_create_transaction(auth_payload):
    return create_transaction(auth_payload)

@transactions_api_bp.route('/transactions/<tx_id>', methods=['GET'])
@handle_errors
@require_auth
def api_get_transaction(tx_id, auth_payload):
    return get_transaction(tx_id, auth_payload)

@transactions_api_bp.route('/transactions/<tx_id>', methods=['PUT'])
@handle_errors
@require_auth
def api_update_transaction(tx_id, auth_payload):
    return update_transaction(tx_id, auth_payload)

@transactions_api_bp.route('/transactions/<tx_id>', methods=['DELETE'])
@handle_errors
@require_auth
def api_delete_transaction(tx_id, auth_payload):
    return delete_transaction(tx_id, auth_payload)
