from flask import Blueprint, request, current_app
from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.helpers import respond_success, respond_error, get_request_payload
from werkzeug.exceptions import Unauthorized, Forbidden
from bson import ObjectId

expenses_bp = Blueprint('expenses', __name__, url_prefix='/expenses')


expense_repo = get_collection('expenses')

@expenses_bp.route('', methods=['POST'])
def create_expense():
    try:
        payload = get_request_payload(request)
        data = request.get_json(force=True)
        if not expense_repo:
            return respond_error('Expenses repository not available', status=500)
        # minimal validation: amount and pond/account
        inserted = expense_repo.create_expense(data)
        return respond_success({'data': {'expenseId': str(inserted)}}, status=201)
    except (Unauthorized, Forbidden) as ue:
        return respond_error(str(ue), status=getattr(ue, 'code', 401))
    except Exception as e:
        current_app.logger.exception('Failed to create expense')
        return respond_error('Server error', status=500)


@expenses_bp.route('', methods=['GET'])
def list_expenses():
    try:
        payload = get_request_payload(request)
        q = {}
        account = request.args.get('account_key')
        if account:
            q['account_key'] = account
        res = expense_repo.find_expenses(q)
        return respond_success({'data': res})
    except (Unauthorized, Forbidden) as ue:
        return respond_error(str(ue), status=getattr(ue, 'code', 401))
    except Exception:
        current_app.logger.exception('Failed to list expenses')
        return respond_error('Server error', status=500)


@expenses_bp.route('/<expense_id>/pay', methods=['POST'])
def pay_expense(expense_id):
    try:
        payload = get_request_payload(request)
        body = request.get_json(force=True)
        # create payment and optionally a transaction
        exp = expense_repo.find_expense({'_id': expense_id})
        if not exp:
            return respond_error('Expense not found', status=404)
        payment_doc = body.get('payment') if isinstance(body, dict) else {}
        tx_doc = body.get('transaction') if isinstance(body, dict) else None
        pay_id, tx_id = expense_repo.create_payment_and_transaction(payment_doc, tx_doc)
        # mark expense paid
        expense_repo.update_expense({'_id': exp['_id']}, {'status': 'paid', 'paymentId': pay_id})
        return respond_success({'data': {'paymentId': str(pay_id), 'transactionId': str(tx_id) if tx_id else None}})
    except (Unauthorized, Forbidden) as ue:
        return respond_error(str(ue), status=getattr(ue, 'code', 401))
    except Exception:
        current_app.logger.exception('Failed to pay expense')
        return respond_error('Server error', status=500)


@expenses_bp.route('/transactions', methods=['POST'])
def create_transaction():
    try:
        payload = get_request_payload(request)
        tx = request.get_json(force=True)
        tx_repo = expense_repo.transactions
        if not tx_repo:
            return respond_error('Transactions repository not available', status=500)
        tid = tx_repo.create_transaction(tx)
        return respond_success({'data': {'transactionId': str(tid)}}, status=201)
    except (Unauthorized, Forbidden) as ue:
        return respond_error(str(ue), status=getattr(ue, 'code', 401))
    except Exception:
        current_app.logger.exception('Failed to create transaction')
        return respond_error('Server error', status=500)


@expenses_bp.route('/payments', methods=['POST'])
def create_payment():
    try:
        payload = get_request_payload(request)
        payment = request.get_json(force=True)
        pay_repo = expense_repo.payments
        if not pay_repo:
            return respond_error('Payments repository not available', status=500)
        res = pay_repo.create_payment(payment)
        return respond_success({'data': {'paymentId': str(res.inserted_id)}}, status=201)
    except (Unauthorized, Forbidden) as ue:
        return respond_error(str(ue), status=getattr(ue, 'code', 401))
    except Exception:
        current_app.logger.exception('Failed to create payment')
        return respond_error('Server error', status=500)


@expenses_bp.route('/payments/<payment_id>', methods=['GET'])
def get_payment(payment_id):
    try:
        payload = get_request_payload(request)
        pay = expense_repo.payments.find_one({'_id': ObjectId(payment_id)})
        if not pay:
            return respond_error('Payment not found', status=404)
        return respond_success({'data': pay})
    except (Unauthorized, Forbidden) as ue:
        return respond_error(str(ue), status=getattr(ue, 'code', 401))
    except Exception:
        current_app.logger.exception('Failed to fetch payment')
        return respond_error('Server error', status=500)


@expenses_bp.route('/bank_statements/import', methods=['POST'])
def import_bank_statement():
    try:
        payload = get_request_payload(request)
        body = request.get_json(force=True)
        bs_repo = expense_repo.bank_statements
        sl_repo = expense_repo.statement_lines
        if not bs_repo or not sl_repo:
            return respond_error('Bank statements repositories not available', status=500)
        stmt = body.get('statement')
        lines = body.get('lines', [])
        res = bs_repo.create(stmt)
        if lines:
            # attach bankStatementId
            for l in lines:
                l['bankStatementId'] = res.inserted_id
            sl_repo.insert_many(lines)
        return respond_success({'data': {'bankStatementId': str(res.inserted_id)}})
    except (Unauthorized, Forbidden) as ue:
        return respond_error(str(ue), status=getattr(ue, 'code', 401))
    except Exception:
        current_app.logger.exception('Failed to import bank statement')
        return respond_error('Server error', status=500)


@expenses_bp.route('/reconcile/by-external', methods=['POST'])
def reconcile_by_external():
    try:
        payload = get_request_payload(request)
        body = request.get_json(force=True)
        bank_account_id = body.get('bankAccountId')
        external_ref = body.get('externalRef')
        if not bank_account_id or not external_ref:
            return respond_error('bankAccountId and externalRef are required', status=400)
        matches = expense_repo.reconcile_by_external_ref(ObjectId(bank_account_id) if not isinstance(bank_account_id, ObjectId) else bank_account_id, external_ref)
        # convert ids to strings for response
        out = []
        for line, payment in matches:
            out.append({'lineId': str(line.get('_id')), 'paymentId': str(payment.get('_id'))})
        return respond_success({'data': out})
    except (Unauthorized, Forbidden) as ue:
        return respond_error(str(ue), status=getattr(ue, 'code', 401))
    except Exception:
        current_app.logger.exception('Failed to reconcile')
        return respond_error('Server error', status=500)


# API blueprint alias
from flask import Blueprint as _Blueprint

expenses_api_bp = _Blueprint('expenses_api', __name__, url_prefix='/api')

@expenses_api_bp.route('/expenses', methods=['POST'])
def api_create_expense():
    return create_expense()

@expenses_api_bp.route('/expenses', methods=['GET'])
def api_list_expenses():
    return list_expenses()

@expenses_api_bp.route('/expenses/<expense_id>/pay', methods=['POST'])
def api_pay_expense(expense_id):
    return pay_expense(expense_id)

# Additional API endpoints
@expenses_api_bp.route('/transactions', methods=['POST'])
def api_create_transaction():
    return create_transaction()

@expenses_api_bp.route('/payments', methods=['POST'])
def api_create_payment():
    return create_payment()

@expenses_api_bp.route('/payments/<payment_id>', methods=['GET'])
def api_get_payment(payment_id):
    return get_payment(payment_id)

@expenses_api_bp.route('/bank_statements/import', methods=['POST'])
def api_import_bank_statement():
    return import_bank_statement()

@expenses_api_bp.route('/reconcile/by-external', methods=['POST'])
def api_reconcile_by_external():
    return reconcile_by_external()
