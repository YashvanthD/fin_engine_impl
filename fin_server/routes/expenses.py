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
