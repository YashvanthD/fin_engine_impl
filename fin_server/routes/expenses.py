from flask import Blueprint, request, current_app
from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.helpers import respond_success, respond_error, get_request_payload
from werkzeug.exceptions import Unauthorized, Forbidden
from bson import ObjectId
from fin_server.services.expense_service import create_expense_with_repo, post_transaction_effects


expenses_bp = Blueprint('expenses', __name__, url_prefix='/expenses')


expense_repo = get_collection('expenses')

@expenses_bp.route('', methods=['POST'])
def create_expense():
    try:
        payload = get_request_payload(request)
        data = request.get_json(force=True)
        if not expense_repo:
            return respond_error('Expenses repository not available', status=500)
        # Use centralized helper to normalize and persist expense documents. This
        # ensures domain links (pond/sampling/stock) are stored in `metadata` and
        # category/type/status/payload are normalized consistently.
        inserted = create_expense_with_repo(data, expense_repo)
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
        import json
        from datetime import datetime

        q = {}
        # basic filters
        account = request.args.get('account_key')
        if account:
            q['account_key'] = account

        # allow comma-separated lists for category/type/status
        def split_list(val):
            if not val:
                return None
            if isinstance(val, (list, tuple)):
                return list(val)
            return [v.strip() for v in val.split(',') if v.strip()]

        category = request.args.get('category')
        if category:
            cats = split_list(category)
            q['category'] = {'$in': cats} if len(cats) > 1 else cats[0]

        typ = request.args.get('type')
        if typ:
            vals = split_list(typ)
            q['type'] = {'$in': vals} if len(vals) > 1 else vals[0]

        status = request.args.get('status')
        if status:
            vals = split_list(status)
            q['status'] = {'$in': vals} if len(vals) > 1 else vals[0]

        # amount range
        min_amount = request.args.get('min_amount') or request.args.get('min')
        max_amount = request.args.get('max_amount') or request.args.get('max')
        amount_q = {}
        try:
            if min_amount is not None:
                amount_q['$gte'] = float(min_amount)
            if max_amount is not None:
                amount_q['$lte'] = float(max_amount)
        except ValueError:
            return respond_error('Invalid amount filter', status=400)
        if amount_q:
            # try to match a top-level amount field; fallback to payload.amount via $or
            q['$or'] = q.get('$or', []) + [{'amount': amount_q}, {'payload.amount': amount_q}]

        # date range: accept ISO8601 or YYYY-MM-DD
        start_date = request.args.get('start_date') or request.args.get('from')
        end_date = request.args.get('end_date') or request.args.get('to')
        date_q = {}
        def parse_date(s):
            if not s:
                return None
            try:
                # try full ISO
                return datetime.fromisoformat(s)
            except Exception:
                try:
                    return datetime.strptime(s, '%Y-%m-%d')
                except Exception:
                    return None

        sd = parse_date(start_date)
        ed = parse_date(end_date)
        if (start_date and not sd) or (end_date and not ed):
            return respond_error('Invalid date format. Use ISO8601 or YYYY-MM-DD', status=400)
        if sd or ed:
            dq = {}
            if sd:
                dq['$gte'] = sd
            if ed:
                dq['$lte'] = ed
            # match either expense `date` or `created_at`
            q['$or'] = q.get('$or', []) + [{'date': dq}, {'created_at': dq}]

        # allow a JSON `filters` query param to pass arbitrary simple filters
        filters_raw = request.args.get('filters')
        if filters_raw:
            try:
                extra = json.loads(filters_raw)
                if isinstance(extra, dict):
                    # merge - do not overwrite explicit params
                    for k, v in extra.items():
                        if k not in q:
                            q[k] = v
            except Exception:
                return respond_error('Invalid JSON in filters parameter', status=400)

        # limit / pagination
        try:
            limit = int(request.args.get('limit') or request.args.get('l') or 100)
        except ValueError:
            return respond_error('Invalid limit', status=400)
        limit = max(1, min(limit, 1000))

        res = expense_repo.find_expenses(q, limit=limit)
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
        res = tx_repo.create_transaction(tx)
        # normalize possible return types
        if isinstance(res, dict):
            tx_id = res.get('inserted_id') or res.get('_id') or res.get('id')
        else:
            tx_id = res
        try:
            if tx_id:
                post_transaction_effects(tx_id)
        except Exception:
            current_app.logger.exception('Failed to post transaction effects for %s', tx_id)
        return respond_success({'data': {'transactionId': str(tx_id) if tx_id else None}}, status=201)
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
        # Use high-level method which will also optionally create a transaction
        tx_doc = payment.get('transaction') if isinstance(payment, dict) else None
        # The ExpensesRepository.create_payment_and_transaction expects (payment_doc, tx_doc)
        try:
            payment_id, tx_id = expense_repo.create_payment_and_transaction(payment, tx_doc)
            # If a transaction was created for the payment, post its accounting effects
            try:
                if tx_id:
                    post_transaction_effects(tx_id)
            except Exception:
                current_app.logger.exception('Failed to post transaction effects for payment tx %s', tx_id)
            return respond_success({'data': {'paymentId': str(payment_id), 'transactionId': str(tx_id) if tx_id else None}}, status=201)
        except Exception:
            current_app.logger.exception('Failed to create payment and transaction')
            return respond_error('Server error', status=500)
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
        inserted_id = getattr(res, 'inserted_id', None) if res is not None else None
        if lines:
            # attach bankStatementId
            for l in lines:
                l['bankStatementId'] = inserted_id
            # use statement_lines repository to insert many
            try:
                sl_repo.insert_many(lines)
            except Exception:
                # fallback to collection
                coll = getattr(sl_repo, 'coll', getattr(sl_repo, 'collection', sl_repo))
                for l in lines:
                    coll.insert_one(l)

            # attempt reconciliation for lines that have externalRef
            for l in lines:
                ext = l.get('externalRef') or l.get('external_ref')
                bank_acc = l.get('bankAccountId') or l.get('bank_account_id')
                if ext and bank_acc:
                    try:
                        matches = expense_repo.reconcile_by_external_ref(bank_acc, ext)
                        # matches returned may be used for logging/audit
                    except Exception:
                        current_app.logger.exception('Failed to reconcile statement line %s', l)
        return respond_success({'data': {'bankStatementId': str(inserted_id)}})
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
