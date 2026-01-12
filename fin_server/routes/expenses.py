"""Expense routes for financial tracking.

This module provides endpoints for:
- Expense creation and listing
- Payments and transactions
- Bank statement import and reconciliation
"""
import json
import logging
from datetime import datetime

from bson import ObjectId
from flask import Blueprint, request

from fin_server.repository.mongo_helper import get_collection
from fin_server.services.expense_service import create_expense_with_repo, post_transaction_effects
from fin_server.utils.decorators import handle_errors, require_auth
from fin_server.utils.helpers import respond_success, respond_error

logger = logging.getLogger(__name__)

# Blueprint
expenses_bp = Blueprint('expenses', __name__, url_prefix='/expenses')

# Repository
expense_repo = get_collection('expenses')


# =============================================================================
# Helper Functions
# =============================================================================

def _split_list(val):
    """Split comma-separated string into list."""
    if not val:
        return None
    if isinstance(val, (list, tuple)):
        return list(val)
    return [v.strip() for v in val.split(',') if v.strip()]


def _parse_date(s):
    """Parse date string (ISO8601 or YYYY-MM-DD)."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        try:
            return datetime.strptime(s, '%Y-%m-%d')
        except Exception:
            return None


def _build_expense_query(args):
    """Build MongoDB query from request args."""
    q = {}

    # Account filter
    account = args.get('account_key')
    if account:
        q['account_key'] = account

    # Category/type/status filters (support comma-separated)
    for field in ['category', 'type', 'status']:
        val = args.get(field)
        if val:
            vals = _split_list(val)
            q[field] = {'$in': vals} if len(vals) > 1 else vals[0]

    # Amount range
    min_amount = args.get('min_amount') or args.get('min')
    max_amount = args.get('max_amount') or args.get('max')
    if min_amount or max_amount:
        amount_q = {}
        if min_amount:
            amount_q['$gte'] = float(min_amount)
        if max_amount:
            amount_q['$lte'] = float(max_amount)
        q['$or'] = q.get('$or', []) + [{'amount': amount_q}, {'payload.amount': amount_q}]

    # Date range
    start_date = args.get('start_date') or args.get('from')
    end_date = args.get('end_date') or args.get('to')
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)

    if sd or ed:
        dq = {}
        if sd:
            dq['$gte'] = sd
        if ed:
            dq['$lte'] = ed
        q['$or'] = q.get('$or', []) + [{'date': dq}, {'created_at': dq}]

    # Extra JSON filters
    filters_raw = args.get('filters')
    if filters_raw:
        extra = json.loads(filters_raw)
        if isinstance(extra, dict):
            for k, v in extra.items():
                if k not in q:
                    q[k] = v

    return q, sd, ed


# =============================================================================
# Expense Endpoints
# =============================================================================

@expenses_bp.route('', methods=['POST'])
@handle_errors
@require_auth
def create_expense(auth_payload):
    """Create a new expense."""
    data = request.get_json(force=True)

    if not expense_repo:
        return respond_error('Expenses repository not available', status=500)

    inserted = create_expense_with_repo(data, expense_repo)
    return respond_success({'data': {'expenseId': str(inserted)}}, status=201)


@expenses_bp.route('', methods=['GET'])
@handle_errors
@require_auth
def list_expenses(auth_payload):
    """List expenses with filters."""
    args = request.args.to_dict()

    # Validate and build query
    try:
        q, sd, ed = _build_expense_query(args)
    except json.JSONDecodeError:
        return respond_error('Invalid JSON in filters parameter', status=400)
    except ValueError as e:
        return respond_error(str(e), status=400)

    # Validate date parsing
    start_date = args.get('start_date') or args.get('from')
    end_date = args.get('end_date') or args.get('to')
    if (start_date and not sd) or (end_date and not ed):
        return respond_error('Invalid date format. Use ISO8601 or YYYY-MM-DD', status=400)

    # Pagination
    try:
        limit = int(args.get('limit') or args.get('l') or 100)
        limit = max(1, min(limit, 1000))
    except ValueError:
        return respond_error('Invalid limit', status=400)

    res = expense_repo.find_expenses(q, limit=limit)
    return respond_success({'data': res})


@expenses_bp.route('/<expense_id>/pay', methods=['POST'])
@handle_errors
@require_auth
def pay_expense(expense_id, auth_payload):
    """Mark an expense as paid."""
    body = request.get_json(force=True)

    exp = expense_repo.find_expense({'_id': expense_id})
    if not exp:
        return respond_error('Expense not found', status=404)

    payment_doc = body.get('payment', {}) if isinstance(body, dict) else {}
    tx_doc = body.get('transaction') if isinstance(body, dict) else None

    pay_id, tx_id = expense_repo.create_payment_and_transaction(payment_doc, tx_doc)
    expense_repo.update_expense({'_id': exp['_id']}, {'status': 'paid', 'paymentId': pay_id})

    return respond_success({
        'data': {
            'paymentId': str(pay_id),
            'transactionId': str(tx_id) if tx_id else None
        }
    })


# =============================================================================
# Transaction Endpoints
# =============================================================================

@expenses_bp.route('/transactions', methods=['POST'])
@handle_errors
@require_auth
def create_transaction(auth_payload):
    """Create a new transaction."""
    tx = request.get_json(force=True)

    tx_repo = expense_repo.transactions
    if not tx_repo:
        return respond_error('Transactions repository not available', status=500)

    res = tx_repo.create_transaction(tx)

    # Normalize return type
    tx_id = res.get('inserted_id') or res.get('_id') or res.get('id') if isinstance(res, dict) else res

    # Post transaction effects (best effort)
    if tx_id:
        try:
            post_transaction_effects(tx_id)
        except Exception:
            logger.exception('Failed to post transaction effects for %s', tx_id)

    return respond_success({'data': {'transactionId': str(tx_id) if tx_id else None}}, status=201)


# =============================================================================
# Payment Endpoints
# =============================================================================

@expenses_bp.route('/payments', methods=['POST'])
@handle_errors
@require_auth
def create_payment(auth_payload):
    """Create a new payment."""
    payment = request.get_json(force=True)

    tx_doc = payment.get('transaction') if isinstance(payment, dict) else None
    payment_id, tx_id = expense_repo.create_payment_and_transaction(payment, tx_doc)

    # Post transaction effects (best effort)
    if tx_id:
        try:
            post_transaction_effects(tx_id)
        except Exception:
            logger.exception('Failed to post transaction effects for payment tx %s', tx_id)

    return respond_success({
        'data': {
            'paymentId': str(payment_id),
            'transactionId': str(tx_id) if tx_id else None
        }
    }, status=201)


@expenses_bp.route('/payments/<payment_id>', methods=['GET'])
@handle_errors
@require_auth
def get_payment(payment_id, auth_payload):
    """Get a payment by ID."""
    pay = expense_repo.payments.find_one({'_id': ObjectId(payment_id)})
    if not pay:
        return respond_error('Payment not found', status=404)
    return respond_success({'data': pay})


# =============================================================================
# Bank Statement Endpoints
# =============================================================================

@expenses_bp.route('/bank_statements/import', methods=['POST'])
@handle_errors
@require_auth
def import_bank_statement(auth_payload):
    """Import a bank statement with lines."""
    body = request.get_json(force=True)

    bs_repo = expense_repo.bank_statements
    sl_repo = expense_repo.statement_lines

    if not bs_repo or not sl_repo:
        return respond_error('Bank statements repositories not available', status=500)

    stmt = body.get('statement')
    lines = body.get('lines', [])

    res = bs_repo.create(stmt)
    inserted_id = getattr(res, 'inserted_id', None) if res is not None else None

    if lines:
        # Attach statement ID to lines
        for line in lines:
            line['bankStatementId'] = inserted_id

        # Insert lines
        try:
            sl_repo.insert_many(lines)
        except Exception:
            coll = getattr(sl_repo, 'coll', getattr(sl_repo, 'collection', sl_repo))
            for line in lines:
                coll.insert_one(line)

        # Reconcile lines with external references
        for line in lines:
            ext = line.get('externalRef') or line.get('external_ref')
            bank_acc = line.get('bankAccountId') or line.get('bank_account_id')
            if ext and bank_acc:
                try:
                    expense_repo.reconcile_by_external_ref(bank_acc, ext)
                except Exception:
                    logger.exception('Failed to reconcile statement line')

    return respond_success({'data': {'bankStatementId': str(inserted_id)}})


@expenses_bp.route('/reconcile/by-external', methods=['POST'])
@handle_errors
@require_auth
def reconcile_by_external(auth_payload):
    """Reconcile payments by external reference."""
    body = request.get_json(force=True)

    bank_account_id = body.get('bankAccountId')
    external_ref = body.get('externalRef')

    if not bank_account_id or not external_ref:
        return respond_error('bankAccountId and externalRef are required', status=400)

    if not isinstance(bank_account_id, ObjectId):
        bank_account_id = ObjectId(bank_account_id)

    matches = expense_repo.reconcile_by_external_ref(bank_account_id, external_ref)

    out = [
        {'lineId': str(line.get('_id')), 'paymentId': str(payment.get('_id'))}
        for line, payment in matches
    ]

    return respond_success({'data': out})


# =============================================================================
# API Blueprint Aliases
# =============================================================================

expenses_api_bp = Blueprint('expenses_api', __name__, url_prefix='/api')

@expenses_api_bp.route('/expenses', methods=['POST'])
@handle_errors
@require_auth
def api_create_expense(auth_payload):
    return create_expense(auth_payload)

@expenses_api_bp.route('/expenses', methods=['GET'])
@handle_errors
@require_auth
def api_list_expenses(auth_payload):
    return list_expenses(auth_payload)

@expenses_api_bp.route('/expenses/<expense_id>/pay', methods=['POST'])
@handle_errors
@require_auth
def api_pay_expense(expense_id, auth_payload):
    return pay_expense(expense_id, auth_payload)

@expenses_api_bp.route('/transactions', methods=['POST'])
@handle_errors
@require_auth
def api_create_transaction(auth_payload):
    return create_transaction(auth_payload)

@expenses_api_bp.route('/payments', methods=['POST'])
@handle_errors
@require_auth
def api_create_payment(auth_payload):
    return create_payment(auth_payload)

@expenses_api_bp.route('/payments/<payment_id>', methods=['GET'])
@handle_errors
@require_auth
def api_get_payment(payment_id, auth_payload):
    return get_payment(payment_id, auth_payload)

@expenses_api_bp.route('/bank_statements/import', methods=['POST'])
@handle_errors
@require_auth
def api_import_bank_statement(auth_payload):
    return import_bank_statement(auth_payload)

@expenses_api_bp.route('/reconcile/by-external', methods=['POST'])
@handle_errors
@require_auth
def api_reconcile_by_external(auth_payload):
    return reconcile_by_external(auth_payload)


# =============================================================================
# Category Endpoints
# =============================================================================

from fin_server.repository.expenses import (
    load_expense_catalog,
    get_top_level_categories,
    get_subcategories,
    validate_category_path,
    search_categories,
    get_category_suggestions,
    get_expense_category_options
)


@expenses_bp.route('/categories', methods=['GET'])
@handle_errors
def get_expense_categories():
    """Get the full expense category catalog.

    Query params:
        flat: If 'true', returns flattened list instead of hierarchical
        level: Filter by level (0=top, 1=sub, 2=detail)
    """
    args = request.args
    flat = args.get('flat', '').lower() == 'true'
    level = args.get('level')

    catalog = load_expense_catalog()

    if flat:
        from fin_server.repository.expenses import flatten_categories
        categories = flatten_categories(catalog)

        if level is not None:
            try:
                level_int = int(level)
                categories = [c for c in categories if c['level'] == level_int]
            except ValueError:
                pass

        return respond_success({'categories': categories})

    return respond_success({'categories': catalog})


@expenses_bp.route('/categories/top', methods=['GET'])
@handle_errors
def get_top_categories():
    """Get top-level expense categories."""
    categories = get_top_level_categories()
    return respond_success({'categories': categories})


@expenses_bp.route('/categories/options', methods=['GET'])
@handle_errors
def get_category_options():
    """Get category options for dropdown/form selection.

    Returns a dict with top-level categories as keys and
    their immediate children as values.
    """
    options = get_expense_category_options()
    return respond_success({'options': options})


@expenses_bp.route('/categories/subcategories', methods=['GET'])
@handle_errors
def get_subcategories_route():
    """Get subcategories for a parent category.

    Query params:
        parent: Parent category path (e.g., "Operational" or "Operational/Utilities")
    """
    parent = request.args.get('parent', '')
    subcategories = get_subcategories(parent)
    return respond_success({
        'parent': parent,
        'subcategories': subcategories
    })


@expenses_bp.route('/categories/validate', methods=['POST'])
@handle_errors
def validate_category():
    """Validate a category path.

    Request body:
        { "path": "Operational/Utilities/Electricity" }
    """
    data = request.get_json(force=True)
    path = data.get('path', '')

    is_valid, error = validate_category_path(path)

    return respond_success({
        'path': path,
        'valid': is_valid,
        'error': error
    })


@expenses_bp.route('/categories/search', methods=['GET'])
@handle_errors
def search_expense_categories():
    """Search categories by name.

    Query params:
        q: Search query (partial match, case-insensitive)
    """
    query = request.args.get('q', '').strip()

    if not query:
        return respond_error('Search query is required', status=400)

    results = search_categories(query)
    return respond_success({'results': results})


@expenses_bp.route('/categories/suggest', methods=['GET'])
@handle_errors
def suggest_categories():
    """Get category path suggestions based on partial input.

    Query params:
        q: Partial input
        limit: Max results (default 10)
    """
    partial = request.args.get('q', '').strip()
    limit = int(request.args.get('limit', 10))

    if not partial:
        return respond_error('Query is required', status=400)

    suggestions = get_category_suggestions(partial, limit)
    return respond_success({'suggestions': suggestions})


# =============================================================================
# Enhanced Expense CRUD with DTO
# =============================================================================

from fin_server.dto.expense_dto import ExpenseDTO, ExpenseStatus


@expenses_bp.route('/<expense_id>', methods=['GET'])
@handle_errors
@require_auth
def get_expense(expense_id, auth_payload):
    """Get a single expense by ID."""
    try:
        oid = ObjectId(expense_id)
        query = {'_id': oid}
    except Exception:
        query = {'expense_id': expense_id}

    expense = expense_repo.find_one(query)
    if not expense:
        return respond_error('Expense not found', status=404)

    try:
        dto = ExpenseDTO.from_doc(expense)
        return respond_success({'expense': dto.to_dict()})
    except Exception:
        expense['_id'] = str(expense.get('_id'))
        return respond_success({'expense': expense})


@expenses_bp.route('/<expense_id>', methods=['PUT'])
@handle_errors
@require_auth
def update_expense(expense_id, auth_payload):
    """Update an expense."""
    data = request.get_json(force=True)

    try:
        oid = ObjectId(expense_id)
        query = {'_id': oid}
    except Exception:
        query = {'expense_id': expense_id}

    existing = expense_repo.find_one(query)
    if not existing:
        return respond_error('Expense not found', status=404)

    # Remove immutable fields
    data.pop('_id', None)
    data.pop('expense_id', None)
    data.pop('created_at', None)

    # Add updated timestamp
    from fin_server.utils.time_utils import get_time_date_dt
    data['updated_at'] = get_time_date_dt(include_time=True).isoformat()

    result = expense_repo.update_one(query, {'$set': data})

    if result.modified_count == 0:
        return respond_error('No changes made', status=400)

    updated = expense_repo.find_one(query)
    try:
        dto = ExpenseDTO.from_doc(updated)
        return respond_success({'expense': dto.to_dict()})
    except Exception:
        updated['_id'] = str(updated.get('_id'))
        return respond_success({'expense': updated})


@expenses_bp.route('/<expense_id>', methods=['DELETE'])
@handle_errors
@require_auth
def delete_expense(expense_id, auth_payload):
    """Delete an expense."""
    try:
        oid = ObjectId(expense_id)
        query = {'_id': oid}
    except Exception:
        query = {'expense_id': expense_id}

    result = expense_repo.delete_one(query)

    if result.deleted_count == 0:
        return respond_error('Expense not found', status=404)

    return respond_success({'deleted': True})


@expenses_bp.route('/<expense_id>/approve', methods=['POST'])
@handle_errors
@require_auth
def approve_expense(expense_id, auth_payload):
    """Approve an expense."""
    data = request.get_json(force=True) or {}

    try:
        oid = ObjectId(expense_id)
        query = {'_id': oid}
    except Exception:
        query = {'expense_id': expense_id}

    existing = expense_repo.find_one(query)
    if not existing:
        return respond_error('Expense not found', status=404)

    dto = ExpenseDTO.from_doc(existing)
    dto.approve(
        approver_id=auth_payload.get('user_key'),
        notes=data.get('notes')
    )

    expense_repo.update_one(query, {'$set': dto.to_db_doc()})

    return respond_success({'expense': dto.to_dict()})


@expenses_bp.route('/<expense_id>/reject', methods=['POST'])
@handle_errors
@require_auth
def reject_expense(expense_id, auth_payload):
    """Reject an expense."""
    data = request.get_json(force=True)
    reason = data.get('reason')

    if not reason:
        return respond_error('Rejection reason is required', status=400)

    try:
        oid = ObjectId(expense_id)
        query = {'_id': oid}
    except Exception:
        query = {'expense_id': expense_id}

    existing = expense_repo.find_one(query)
    if not existing:
        return respond_error('Expense not found', status=404)

    dto = ExpenseDTO.from_doc(existing)
    dto.reject(
        rejector_id=auth_payload.get('user_key'),
        reason=reason
    )

    expense_repo.update_one(query, {'$set': dto.to_db_doc()})

    return respond_success({'expense': dto.to_dict()})


@expenses_bp.route('/<expense_id>/cancel', methods=['POST'])
@handle_errors
@require_auth
def cancel_expense(expense_id, auth_payload):
    """Cancel an expense."""
    data = request.get_json(force=True) or {}
    reason = data.get('reason')

    try:
        oid = ObjectId(expense_id)
        query = {'_id': oid}
    except Exception:
        query = {'expense_id': expense_id}

    existing = expense_repo.find_one(query)
    if not existing:
        return respond_error('Expense not found', status=404)

    dto = ExpenseDTO.from_doc(existing)
    dto.cancel(reason=reason)

    expense_repo.update_one(query, {'$set': dto.to_db_doc()})

    return respond_success({'expense': dto.to_dict()})


# =============================================================================
# Expense Analytics/Summary
# =============================================================================

@expenses_bp.route('/summary', methods=['GET'])
@handle_errors
@require_auth
def get_expense_summary(auth_payload):
    """Get expense summary/analytics.

    Query params:
        account_key: Filter by account
        start_date: Start date (ISO)
        end_date: End date (ISO)
        group_by: Group by field (category, subcategory, type, status, month)
    """
    args = request.args.to_dict()
    account_key = args.get('account_key') or auth_payload.get('account_key')
    group_by = args.get('group_by', 'category')

    # Build match stage
    match = {'account_key': account_key} if account_key else {}

    start_date = _parse_date(args.get('start_date'))
    end_date = _parse_date(args.get('end_date'))
    if start_date or end_date:
        date_filter = {}
        if start_date:
            date_filter['$gte'] = start_date.isoformat()
        if end_date:
            date_filter['$lte'] = end_date.isoformat()
        match['created_at'] = date_filter

    # Build group stage
    if group_by == 'month':
        group_id = {'$substr': ['$created_at', 0, 7]}  # YYYY-MM
    else:
        group_id = f'${group_by}'

    pipeline = [
        {'$match': match},
        {'$group': {
            '_id': group_id,
            'total': {'$sum': '$amount'},
            'count': {'$sum': 1},
            'avg': {'$avg': '$amount'},
            'min': {'$min': '$amount'},
            'max': {'$max': '$amount'}
        }},
        {'$sort': {'total': -1}}
    ]

    try:
        coll = expense_repo.collection if hasattr(expense_repo, 'collection') else expense_repo
        results = list(coll.aggregate(pipeline))

        # Format results
        summary = []
        for r in results:
            summary.append({
                group_by: r['_id'],
                'total': r['total'],
                'count': r['count'],
                'average': round(r['avg'], 2) if r['avg'] else 0,
                'min': r['min'],
                'max': r['max']
            })

        # Calculate grand totals
        grand_total = sum(r['total'] or 0 for r in results)
        total_count = sum(r['count'] for r in results)

        return respond_success({
            'summary': summary,
            'grandTotal': grand_total,
            'totalCount': total_count,
            'groupBy': group_by
        })
    except Exception as e:
        logger.exception('Error generating expense summary')
        return respond_error('Failed to generate summary', status=500)


@expenses_bp.route('/by-pond/<pond_id>', methods=['GET'])
@handle_errors
@require_auth
def get_expenses_by_pond(pond_id, auth_payload):
    """Get all expenses for a specific pond."""
    query = {
        '$or': [
            {'pond_id': pond_id},
            {'metadata.pond_id': pond_id}
        ]
    }

    try:
        limit = int(request.args.get('limit', 100))
    except ValueError:
        limit = 100

    expenses = list(expense_repo.find(query).sort('created_at', -1).limit(limit))

    result = []
    for e in expenses:
        try:
            dto = ExpenseDTO.from_doc(e)
            result.append(dto.to_dict())
        except Exception:
            e['_id'] = str(e.get('_id'))
            result.append(e)

    return respond_success({'expenses': result, 'pondId': pond_id})


# Add category routes to API blueprint
@expenses_api_bp.route('/expenses/categories', methods=['GET'])
@handle_errors
def api_get_expense_categories():
    return get_expense_categories()

@expenses_api_bp.route('/expenses/categories/options', methods=['GET'])
@handle_errors
def api_get_category_options():
    return get_category_options()

@expenses_api_bp.route('/expenses/categories/search', methods=['GET'])
@handle_errors
def api_search_categories():
    return search_expense_categories()

@expenses_api_bp.route('/expenses/<expense_id>', methods=['GET'])
@handle_errors
@require_auth
def api_get_expense(expense_id, auth_payload):
    return get_expense(expense_id, auth_payload)

@expenses_api_bp.route('/expenses/<expense_id>', methods=['PUT'])
@handle_errors
@require_auth
def api_update_expense(expense_id, auth_payload):
    return update_expense(expense_id, auth_payload)

@expenses_api_bp.route('/expenses/<expense_id>', methods=['DELETE'])
@handle_errors
@require_auth
def api_delete_expense(expense_id, auth_payload):
    return delete_expense(expense_id, auth_payload)

@expenses_api_bp.route('/expenses/<expense_id>/approve', methods=['POST'])
@handle_errors
@require_auth
def api_approve_expense(expense_id, auth_payload):
    return approve_expense(expense_id, auth_payload)

@expenses_api_bp.route('/expenses/<expense_id>/reject', methods=['POST'])
@handle_errors
@require_auth
def api_reject_expense(expense_id, auth_payload):
    return reject_expense(expense_id, auth_payload)

@expenses_api_bp.route('/expenses/summary', methods=['GET'])
@handle_errors
@require_auth
def api_get_expense_summary(auth_payload):
    return get_expense_summary(auth_payload)
