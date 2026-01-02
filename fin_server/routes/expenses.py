from flask import Blueprint, request, current_app
from bson import ObjectId
from fin_server.repository.mongo_helper import MongoRepositorySingleton
from fin_server.security.authentication import get_auth_payload
from fin_server.exception.UnauthorizedError import UnauthorizedError
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc, parse_iso_or_epoch

expenses_bp = Blueprint('expenses', __name__, url_prefix='/expenses')
repo_singleton = MongoRepositorySingleton.get_instance()


@expenses_bp.route('', methods=['OPTIONS'])
def expenses_options_root():
    return current_app.make_default_options_response()


@expenses_bp.route('', methods=['GET'])
def list_expenses():
    try:
        payload = get_auth_payload(request)
        args = request.args or {}
        start_raw = args.get('startDate') or args.get('start_date') or args.get('from')
        end_raw = args.get('endDate') or args.get('end_date') or args.get('to')
        pond = args.get('pondId') or args.get('pond_id') or args.get('pond')
        species = args.get('species')
        tx_ref = args.get('transaction_ref') or args.get('transactionRef')
        try:
            limit = int(args.get('limit', 50))
            if limit < 1:
                limit = 50
        except Exception:
            limit = 50

        q = {}
        acct = payload.get('account_key')
        if acct:
            q['account_key'] = acct
        if pond:
            q['pond_id'] = pond
        if species:
            q['species'] = species
        if tx_ref:
            q['transaction_ref'] = tx_ref

        # date range on created_at
        start_dt = parse_iso_or_epoch(start_raw)
        end_dt = parse_iso_or_epoch(end_raw)
        if start_dt or end_dt:
            date_q = {}
            if start_dt is not None:
                date_q['$gte'] = start_dt
            if end_dt is not None:
                date_q['$lte'] = end_dt
            q['created_at'] = date_q

        coll = repo_singleton.get_collection('expenses')
        cursor = coll.find(q).sort([('created_at', -1)]).limit(limit)
        recs = list(cursor)
        out = [normalize_doc(r) for r in recs]
        return respond_success(out)
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        current_app.logger.exception('Error in list_expenses')
        return respond_error('Server error', status=500)


@expenses_bp.route('', methods=['POST'])
def create_expense():
    try:
        payload = get_auth_payload(request)
        data = request.get_json(force=True)
        # attach recorded_by/account_key from token if not present
        data['recorded_by'] = data.get('recorded_by') or payload.get('user_key')
        data['account_key'] = data.get('account_key') or payload.get('account_key')
        # Use repository to create (it will create transaction and attach transaction_ref when available)
        expenses_repo = repo_singleton.expenses
        if expenses_repo:
            res = expenses_repo.create(data)
            inserted_id = getattr(res, 'inserted_id', None)
            doc = repo_singleton.get_collection('expenses').find_one({'_id': inserted_id})
            return respond_success(normalize_doc(doc), status=201)
        else:
            # fallback direct insert
            coll = repo_singleton.get_collection('expenses')
            rr = coll.insert_one(data)
            doc = coll.find_one({'_id': rr.inserted_id})
            return respond_success(normalize_doc(doc), status=201)
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        current_app.logger.exception('Error in create_expense')
        return respond_error('Server error', status=500)


@expenses_bp.route('/<expense_id>', methods=['GET'])
def get_expense(expense_id):
    try:
        payload = get_auth_payload(request)
        coll = repo_singleton.get_collection('expenses')
        query = None
        try:
            query = {'_id': ObjectId(expense_id)}
        except Exception:
            query = {'transaction_ref': expense_id}
        doc = coll.find_one(query)
        if not doc:
            return respond_error('Expense not found', status=404)
        # enforce account scoping
        acct = payload.get('account_key')
        if acct and doc.get('account_key') and doc.get('account_key') != acct:
            return respond_error('Not authorized', status=403)
        return respond_success(normalize_doc(doc))
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        current_app.logger.exception('Error in get_expense')
        return respond_error('Server error', status=500)


@expenses_bp.route('/<expense_id>', methods=['PUT'])
def update_expense(expense_id):
    try:
        payload = get_auth_payload(request)
        data = request.get_json(force=True)
        coll = repo_singleton.get_collection('expenses')
        query = None
        try:
            query = {'_id': ObjectId(expense_id)}
        except Exception:
            query = {'transaction_ref': expense_id}
        existing = coll.find_one(query)
        if not existing:
            return respond_error('Expense not found', status=404)
        acct = payload.get('account_key')
        if acct and existing.get('account_key') and existing.get('account_key') != acct:
            return respond_error('Not authorized', status=403)
        # prevent changing transaction_ref directly
        data.pop('transaction_ref', None)
        coll.update_one({'_id': existing.get('_id')}, {'$set': data})
        updated = coll.find_one({'_id': existing.get('_id')})
        return respond_success(normalize_doc(updated))
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        current_app.logger.exception('Error in update_expense')
        return respond_error('Server error', status=500)


@expenses_bp.route('/<expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    try:
        payload = get_auth_payload(request)
        coll = repo_singleton.get_collection('expenses')
        try:
            query = {'_id': ObjectId(expense_id)}
        except Exception:
            query = {'transaction_ref': expense_id}
        existing = coll.find_one(query)
        if not existing:
            return respond_error('Expense not found', status=404)
        acct = payload.get('account_key')
        if acct and existing.get('account_key') and existing.get('account_key') != acct:
            return respond_error('Not authorized', status=403)
        coll.delete_one({'_id': existing.get('_id')})
        return respond_success({'deleted': True})
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        current_app.logger.exception('Error in delete_expense')
        return respond_error('Server error', status=500)


# API blueprint for /api/expenses
from flask import Blueprint as _Blueprint
expenses_api_bp = _Blueprint('expenses_api', __name__, url_prefix='/api')

@expenses_api_bp.route('/expenses', methods=['GET'])
def api_list_expenses():
    return list_expenses()

@expenses_api_bp.route('/expenses', methods=['POST'])
def api_create_expense():
    return create_expense()

@expenses_api_bp.route('/expenses/<expense_id>', methods=['GET'])
def api_get_expense(expense_id):
    return get_expense(expense_id)

@expenses_api_bp.route('/expenses/<expense_id>', methods=['PUT'])
def api_update_expense(expense_id):
    return update_expense(expense_id)

@expenses_api_bp.route('/expenses/<expense_id>', methods=['DELETE'])
def api_delete_expense(expense_id):
    return delete_expense(expense_id)

