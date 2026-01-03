from flask import Blueprint, request, current_app
from bson import ObjectId

from fin_server.repository.mongo_helper import get_collection
from fin_server.security.authentication import get_auth_payload
from fin_server.exception.UnauthorizedError import UnauthorizedError
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc, parse_iso_or_epoch

transactions_bp = Blueprint('transactions', __name__, url_prefix='/transactions')

transactions_repo = get_collection('transactions')

@transactions_bp.route('', methods=['OPTIONS'])
def transactions_options_root():
    return current_app.make_default_options_response()


@transactions_bp.route('', methods=['GET'])
def list_transactions():
    try:
        payload = get_auth_payload(request)
        args = request.args or {}
        start_raw = args.get('startDate') or args.get('start_date') or args.get('from')
        end_raw = args.get('endDate') or args.get('end_date') or args.get('to')
        pond = args.get('pondId') or args.get('pond_id') or args.get('pond')
        species = args.get('species')
        tx_type = args.get('type') or args.get('tx_type')
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
        if tx_type:
            q['type'] = tx_type

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

        cursor = transactions_repo.find(q).sort([('created_at', -1)]).limit(limit)
        recs = list(cursor)
        out = [normalize_doc(r) for r in recs]
        return respond_success(out)
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        current_app.logger.exception('Error in list_transactions')
        return respond_error('Server error', status=500)


@transactions_bp.route('', methods=['POST'])
def create_transaction():
    try:
        payload = get_auth_payload(request)
        data = request.get_json(force=True)
        data['recorded_by'] = data.get('recorded_by') or payload.get('user_key')
        data['account_key'] = data.get('account_key') or payload.get('account_key')
        res = transactions_repo.create_transaction(data)
        inserted_id = getattr(res, 'inserted_id', None)
        doc = transactions_repo.find_one({'_id': inserted_id})
        return respond_success(normalize_doc(doc), status=201)
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        current_app.logger.exception('Error in create_transaction')
        return respond_error('Server error', status=500)


@transactions_bp.route('/<tx_id>', methods=['GET'])
def get_transaction(tx_id):
    try:
        payload = get_auth_payload(request)
        query = None
        try:
            query = {'_id': ObjectId(tx_id)}
        except Exception:
            query = {'transaction_id': tx_id}
        doc = transactions_repo.find_one(query)
        if not doc:
            return respond_error('Transaction not found', status=404)
        acct = payload.get('account_key')
        if acct and doc.get('account_key') and doc.get('account_key') != acct:
            return respond_error('Not authorized', status=403)
        return respond_success(normalize_doc(doc))
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        current_app.logger.exception('Error in get_transaction')
        return respond_error('Server error', status=500)


@transactions_bp.route('/<tx_id>', methods=['PUT'])
def update_transaction(tx_id):
    try:
        payload = get_auth_payload(request)
        data = request.get_json(force=True)
        try:
            query = {'_id': ObjectId(tx_id)}
        except Exception:
            query = {'transaction_id': tx_id}
        existing = transactions_repo.find_one(query)
        if not existing:
            return respond_error('Transaction not found', status=404)
        acct = payload.get('account_key')
        if acct and existing.get('account_key') and existing.get('account_key') != acct:
            return respond_error('Not authorized', status=403)
        transactions_repo.update_one({'_id': existing.get('_id')}, {'$set': data})
        updated = transactions_repo.find_one({'_id': existing.get('_id')})
        return respond_success(normalize_doc(updated))
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        current_app.logger.exception('Error in update_transaction')
        return respond_error('Server error', status=500)


@transactions_bp.route('/<tx_id>', methods=['DELETE'])
def delete_transaction(tx_id):
    try:
        payload = get_auth_payload(request)
        try:
            query = {'_id': ObjectId(tx_id)}
        except Exception:
            query = {'transaction_id': tx_id}
        existing = transactions_repo.find_one(query)
        if not existing:
            return respond_error('Transaction not found', status=404)
        acct = payload.get('account_key')
        if acct and existing.get('account_key') and existing.get('account_key') != acct:
            return respond_error('Not authorized', status=403)
        transactions_repo.delete_one({'_id': existing.get('_id')})
        return respond_success({'deleted': True})
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        current_app.logger.exception('Error in delete_transaction')
        return respond_error('Server error', status=500)


# API blueprint
from flask import Blueprint as _Blueprint
transactions_api_bp = _Blueprint('transactions_api', __name__, url_prefix='/api')

@transactions_api_bp.route('/transactions', methods=['GET'])
def api_list_transactions():
    return list_transactions()

@transactions_api_bp.route('/transactions', methods=['POST'])
def api_create_transaction():
    return create_transaction()

@transactions_api_bp.route('/transactions/<tx_id>', methods=['GET'])
def api_get_transaction(tx_id):
    return get_transaction(tx_id)

@transactions_api_bp.route('/transactions/<tx_id>', methods=['PUT'])
def api_update_transaction(tx_id):
    return update_transaction(tx_id)

@transactions_api_bp.route('/transactions/<tx_id>', methods=['DELETE'])
def api_delete_transaction(tx_id):
    return delete_transaction(tx_id)
