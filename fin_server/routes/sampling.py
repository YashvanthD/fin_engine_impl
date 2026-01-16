from flask import Blueprint, request, current_app

from fin_server.dto.growth_dto import GrowthRecordDTO
from fin_server.exception.UnauthorizedError import UnauthorizedError
from fin_server.repository.fish.stock_repository import StockRepository
from fin_server.repository.mongo_helper import get_collection
from fin_server.routes.fish import fish_analytics_repo
from fin_server.routes.pond_event import fish_activity_repo
from fin_server.security.authentication import get_auth_payload
from fin_server.utils.generator import generate_sampling_id
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc, parse_iso_or_epoch
from fin_server.utils.validation import compute_total_amount_from_payload
from fin_server.services.sampling_service import perform_buy_sampling
from fin_server.services.expense_service import handle_sampling_deletion

sampling_bp = Blueprint('sampling', __name__, url_prefix='/api/sampling')

sampling_repo = get_collection('sampling')
pond_repo = get_collection('pond')
fish_repo = get_collection('fish')
expenses_repo = get_collection('expenses')
pond_event_repo = get_collection('pond_event')
fish_mapping_repo = get_collection('fish_mapping')

@sampling_bp.route('', methods=['POST'])
@sampling_bp.route('/', methods=['POST'])
def create_sampling_route():
    try:
        # Short-circuit preflight OPTIONS here to avoid calling auth logic
        if request.method == 'OPTIONS':
            return respond_success({}, status=200)
        payload = get_auth_payload(request)
        data = request.get_json(force=True)
        # Build DTO from request
        dto = GrowthRecordDTO.from_request(data)
        dto.recordedBy = payload.get('user_key')
        dto.user_key = payload.get('user_key')  # Who performed the action
        dto.account_key = payload.get('account_key')  # Which organization
        # Normalize extra
        dto.extra = dto.extra or {}
        dto.extra.setdefault('type', 'sampling')
        dto.extra['account_key'] = payload.get('account_key')  # Also store in extra for backward compat
        dto.extra['user_key'] = payload.get('user_key')  # Also store in extra for backward compat

        # Ensure sampling_id exists
        if not dto.extra.get('sampling_id'):
            dto.extra['sampling_id'] = generate_sampling_id()

        # Compute total amount if not provided
        total_amount = compute_total_amount_from_payload(data, dto)
        if total_amount is not None:
            dto.extra['totalAmount'] = total_amount

        # Persist sampling
        res = dto.save(repo=sampling_repo)
        inserted_id = getattr(res, 'inserted_id', res)
        dto.id = str(inserted_id) if inserted_id is not None else None

        # Detect buy vs sample
        extra = dto.extra or {}
        # Sampling API is treated as buy-only. Use canonical fields only.
        is_buy = True
        buy_count = None
        if 'total_count' in extra:
            buy_count = int(extra['total_count'])
        elif 'totalCount' in extra:
            buy_count = int(extra['totalCount'])
        elif getattr(dto, 'sampleSize', None) is not None:
            buy_count = int(dto.sampleSize)

        # If this is a buy/purchase sampling, persist the total_count in DTO extra so it is stored and returned
        if is_buy and buy_count is not None:
            dto.extra['total_count'] = int(buy_count)

        # Delegate the buy/sampling post-processing to the shared service
        try:
            repos = {
                'sampling': sampling_repo,
                'pond': pond_repo,
                'fish': fish_repo,
                'stock': StockRepository(),
                'fish_activity': fish_activity_repo,
                'fish_analytics': fish_analytics_repo,
                'expenses': expenses_repo,
                'fish_mapping': fish_mapping_repo,
                'pond_event': pond_event_repo
            }
            # Run synchronously here (or spawn a background task if desired)
            svc_res = perform_buy_sampling(dto, payload.get('account_key'), repos)
            # Optionally attach expense id to DTO extra
            if svc_res.get('expense_id'):
                dto.extra['expense_id'] = svc_res.get('expense_id')
        except Exception:
            current_app.logger.exception('Error in perform_buy_sampling')
            raise
        return respond_success(dto.to_dict(), status=201)
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        current_app.logger.exception('Error in create_sampling_route')
        return respond_error('Server error', status=500)

@sampling_bp.route('/<pond_id>', methods=['GET'])
def list_sampling_for_pond_route(pond_id):
    try:
        # Query canonical pond_id field
        recs = list(sampling_repo.find({'pond_id': pond_id}).sort('created_at', -1))
        out = []
        for r in recs:
            ro = normalize_doc(r)
            try:
                dto = GrowthRecordDTO.from_doc(ro)
                out.append(dto.to_dict())
            except Exception:
                out.append(ro)
        return respond_success(out)
    except Exception:
        current_app.logger.exception('Error in list_sampling_for_pond_route')
        return respond_error('Server error', status=500)

# New: GET /sampling/history
@sampling_bp.route('/history', methods=['GET'])
def get_sampling_history():
    """Return sampling history with optional filters:
    - startDate / start_date (ISO or epoch)
    - endDate / end_date
    - pondId / pond_id
    - species
    - limit (default 10)
    """
    try:
        args = request.args or {}
        start_raw = args.get('startDate') or args.get('start_date') or args.get('from')
        end_raw = args.get('endDate') or args.get('end_date') or args.get('to')
        pond = args.get('pondId') or args.get('pond_id') or args.get('pond')
        species = args.get('species')
        # limit default 10
        try:
            limit = int(args.get('limit', 10))
            if limit < 1:
                limit = 10
        except Exception:
            limit = 10

        # build mongo filter
        q = {}
        if pond:
            q['pond_id'] = pond
        if species:
            q['species'] = species

        # date parsing - use parse_iso_or_epoch which returns aware IST datetime
        start_dt = parse_iso_or_epoch(start_raw)
        end_dt = parse_iso_or_epoch(end_raw)
        # If we have datetimes, compare against sampling_date (stored as ISO string) by converting to ISO
        date_query = {}
        if start_dt is not None:
            date_query['$gte'] = start_dt.isoformat()
        if end_dt is not None:
            date_query['$lte'] = end_dt.isoformat()
        if date_query:
            q['sampling_date'] = date_query

        cursor = sampling_repo.find(q).sort([('sampling_date', -1), ('created_at', -1)]).limit(limit)
        recs = list(cursor)
        out = []
        for r in recs:
            ro = normalize_doc(r)
            try:
                dto = GrowthRecordDTO.from_doc(ro)
                out.append(dto.to_dict())
            except Exception:
                out.append(ro)
        return respond_success(out)
    except Exception:
        current_app.logger.exception('Error in get_sampling_history')
        return respond_error('Server error', status=500)


# PUT /sampling/<sampling_id> - correct an existing sampling record
@sampling_bp.route('/<sampling_id>', methods=['PUT'])
def update_sampling_route(sampling_id):
    try:
        payload = get_auth_payload(request)
        data = request.get_json(force=True)

        # Try to resolve sampling by _id (ObjectId) or by sampling_id field
        query = None
        try:
            from bson import ObjectId
            query = {'_id': ObjectId(sampling_id)}
        except Exception:
            # not an ObjectId
            query = {'sampling_id': sampling_id}

        existing = sampling_repo.find_one(query)
        if not existing:
            # Try alternative: direct sampling_id match
            existing = sampling_repo.find_one({'sampling_id': sampling_id})
        if not existing:
            return respond_error('Sampling record not found', status=404)

        # If account scoping exists on records, enforce it
        acct = payload.get('account_key')
        if acct and existing.get('account_key') and existing.get('account_key') != acct:
            return respond_error('Not authorized to modify this sampling (account mismatch)', status=403)

        # Map request keys to DB fields; only set fields explicitly present in the request
        key_map = {
            'pondId': 'pond_id', 'pond_id': 'pond_id', 'pond': 'pond_id',
            'species': 'species',
            'samplingDate': 'sampling_date', 'sampling_date': 'sampling_date',
            'sampleSize': 'sample_size', 'sample_size': 'sample_size',
            'averageWeight': 'average_weight', 'average_weight': 'average_weight',
            'averageLength': 'average_length', 'average_length': 'average_length',
            'survivalRate': 'survival_rate', 'survival_rate': 'survival_rate',
            'feedConversionRatio': 'feed_conversion_ratio', 'feed_conversion_ratio': 'feed_conversion_ratio',
            'cost': 'cost', 'cost_amount': 'cost', 'total_cost': 'total_cost',
            'totalCount': 'total_count', 'total_count': 'total_count',
             'notes': 'notes'
         }

        update_fields = {}
        # normalize incoming keys presence and set corresponding db fields
        for k, dbk in key_map.items():
            if k in data:
                update_fields[dbk] = data.get(k)

        # Prepare delta handling for stock/expense when total_count or total_cost are being updated
        delta_stock = None
        delta_amount = None
        old_total_count = None
        old_total_cost = None
        existing_extra = existing.get('extra') or {}
        # source old values
        try:
            if 'total_count' in existing:
                old_total_count = int(float(existing.get('total_count') or 0))
            elif 'totalCount' in existing:
                old_total_count = int(float(existing.get('totalCount') or 0))
            elif isinstance(existing_extra, dict) and ('total_count' in existing_extra or 'totalCount' in existing_extra):
                old_total_count = int(float(existing_extra.get('total_count') or existing_extra.get('totalCount') or 0))
        except Exception:
            old_total_count = None
        try:
            if 'total_cost' in existing:
                old_total_cost = float(existing.get('total_cost') or 0)
            elif 'totalAmount' in existing:
                old_total_cost = float(existing.get('totalAmount') or 0)
            elif isinstance(existing_extra, dict) and ('total_amount' in existing_extra or 'totalAmount' in existing_extra):
                old_total_cost = float(existing_extra.get('total_amount') or existing_extra.get('totalAmount') or 0)
        except Exception:
            old_total_cost = None

        # compute new values from incoming request
        new_total_count = None
        if 'totalCount' in data:
            try:
                new_total_count = int(float(data.get('totalCount')))
            except Exception:
                new_total_count = None
        elif 'total_count' in data:
            try:
                new_total_count = int(float(data.get('total_count')))
            except Exception:
                new_total_count = None
        elif isinstance(data.get('extra'), dict) and ('total_count' in data.get('extra') or 'totalCount' in data.get('extra')):
            try:
                new_total_count = int(float(data.get('extra').get('total_count') or data.get('extra').get('totalCount')))
            except Exception:
                new_total_count = None

        if new_total_count is not None and old_total_count is not None:
            try:
                delta_stock = int(new_total_count) - int(old_total_count)
            except Exception:
                delta_stock = None

        # total cost delta
        new_total_cost = None
        if 'totalAmount' in data:
            try:
                new_total_cost = float(data.get('totalAmount'))
            except Exception:
                new_total_cost = None
        elif 'total_cost' in data:
            try:
                new_total_cost = float(data.get('total_cost'))
            except Exception:
                new_total_cost = None
        elif isinstance(data.get('extra'), dict) and ('totalAmount' in data.get('extra') or 'total_amount' in data.get('extra')):
            try:
                new_total_cost = float(data.get('extra').get('totalAmount') or data.get('extra').get('total_amount'))
            except Exception:
                new_total_cost = None
        if new_total_cost is not None and old_total_cost is not None:
            try:
                delta_amount = float(new_total_cost) - float(old_total_cost)
            except Exception:
                delta_amount = None

        # Remove None-valued fields from updates (do not store nulls)
        update_fields = {k: v for k, v in update_fields.items() if v is not None}
        if not update_fields:
            return respond_error('No updatable fields provided', status=400)

        # Apply update
        try:
            res = sampling_repo.update_one({'_id': existing.get('_id')}, {'$set': update_fields})
        except Exception:
            return respond_error('Failed to update sampling record', status=500)

        stock_id = None
        # If there is a delta in stock, apply incremental update rather than re-processing a full buy
        try:
            if delta_stock and delta_stock != 0:
                # resolve stock_id from existing sampling if present, else use sampling_id
                stock_id = existing.get('stock_id') or (existing.get('extra') or {}).get('stock_id') or existing.get('sampling_id') or existing.get('_id')
                # Use StockRepository transactional update when available
                sr = StockRepository()
                ok_tx = False
                try:
                    ok_tx = sr.add_stock_transactional(payload.get('account_key'), existing.get('pond_id') or existing.get('pondId') or payload.get('pond_id'), existing.get('species') or existing.get('species_code'), delta_stock, average_weight=update_fields.get('average_weight') or update_fields.get('averageWeight') or None, sampling_id=stock_id, recorded_by=payload.get('user_key'))
                except Exception:
                    ok_tx = False
                if not ok_tx:
                    # fallback to pond_repo.update_stock
                    try:
                        pond_repo.update_stock(existing.get('pond_id') or existing.get('pondId') or payload.get('pond_id'), existing.get('species') or existing.get('species_code'), delta_stock, average_weight=update_fields.get('average_weight') or None, sampling_id=stock_id)
                    except Exception:
                        current_app.logger.exception('Failed to apply delta_stock update')
        except Exception:
            current_app.logger.exception('Error handling delta stock update')

        # If there's a delta in amount, create an expense for positive delta (additional buy), for negative delta you might create reversal (not implemented)
        try:
            if delta_amount and delta_amount > 0 and expenses_repo:
                expense_doc = {
                    'pond_id': existing.get('pond_id') or existing.get('pondId'),
                    'amount': float(delta_amount),
                    'currency': 'INR',
                    'recorded_by': payload.get('user_key'),
                    'account_key': payload.get('account_key'),
                    'category': 'asset', 'action': 'buy', 'type': 'fish',
                    'metadata': {'sampling_id': existing.get('sampling_id') or existing.get('_id'), 'stock_id': stock_id}
                }
                try:
                    if hasattr(expenses_repo, 'create_expense'):
                        expenses_repo.create_expense(expense_doc)
                    elif hasattr(expenses_repo, 'create'):
                        expenses_repo.create(expense_doc)
                    else:
                        expenses_repo.insert_one(expense_doc)
                except Exception:
                    current_app.logger.exception('Failed to create delta expense')
        except Exception:
            current_app.logger.exception('Error handling delta amount')

        updated = sampling_repo.find_one({'_id': existing.get('_id')})
        # Normalize and try to use DTO for response
        ro = normalize_doc(updated)
        try:
            dto = GrowthRecordDTO.from_doc(ro)
            # If this update includes buy-related fields, run the buy sampling service to apply side-effects
            try:
                if 'total_count' in update_fields or 'total_cost' in update_fields:
                    repos = {
                        'sampling': sampling_repo,
                        'pond': pond_repo,
                        'fish': fish_repo,
                        'stock': StockRepository(),
                        'fish_activity': fish_activity_repo,
                        'fish_analytics': fish_analytics_repo,
                        'expenses': expenses_repo,
                        'fish_mapping': fish_mapping_repo,
                        'pond_event': pond_event_repo
                    }
                    perform_buy_sampling(dto, payload.get('account_key'), repos)
            except Exception:
                current_app.logger.exception('Error while running buy sampling service on update')
            return respond_success(dto.to_dict())
        except Exception:
            return respond_success(ro)
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        current_app.logger.exception('Error in update_sampling_route')
        return respond_error('Server error', status=500)

# DELETE /sampling/<sampling_id> - remove a sampling record
@sampling_bp.route('/<sampling_id>', methods=['DELETE'])
def delete_sampling_route(sampling_id):
    """Delete a sampling record and cascade cleanup related data."""
    try:
        payload = get_auth_payload(request)
        account_key = payload.get('account_key')

        # Resolve sampling by _id (ObjectId) or sampling_id
        query = None
        try:
            from bson import ObjectId
            query = {'_id': ObjectId(sampling_id)}
        except Exception:
            query = {'sampling_id': sampling_id}

        existing = sampling_repo.find_one(query)
        if not existing:
            existing = sampling_repo.find_one({'sampling_id': sampling_id})
        if not existing:
            return respond_error('Sampling record not found', status=404)

        # enforce account scoping if present on records
        if account_key and existing.get('account_key') and existing.get('account_key') != account_key:
            return respond_error('Not authorized to delete this sampling (account mismatch)', status=403)

        # Get the actual sampling_id for cleanup
        actual_sampling_id = existing.get('sampling_id') or str(existing.get('_id'))

        # perform business cleanup: cancel expenses, delete linked transactions, decrement counts, remove analytics/activity
        current_app.logger.info(f'Deleting sampling {actual_sampling_id} with cascade cleanup')
        summary = handle_sampling_deletion(actual_sampling_id)

        # finally remove the sampling document itself
        deleted = False
        try:
            # Try by sampling_id first
            del_res = sampling_repo.delete({'sampling_id': actual_sampling_id})
            if del_res and getattr(del_res, 'deleted_count', 0) > 0:
                deleted = True
        except Exception:
            pass

        if not deleted and existing.get('_id'):
            # Fallback: try by _id
            try:
                del_res = sampling_repo.delete({'_id': existing.get('_id')})
                if del_res and getattr(del_res, 'deleted_count', 0) > 0:
                    deleted = True
            except Exception:
                current_app.logger.exception('Failed to delete sampling document')

        if not deleted:
            return respond_error('Failed to delete sampling record', status=500)

        current_app.logger.info(f'Deleted sampling {actual_sampling_id}, cleanup summary: {summary}')
        return respond_success({'deleted': True, 'cleanup_summary': summary})
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        current_app.logger.exception('Error in delete_sampling_route')
        return respond_error('Server error', status=500)

from flask import Blueprint as _Blueprint

sampling_api_bp = _Blueprint('sampling_api', __name__, url_prefix='/api')

@sampling_api_bp.route('/sampling', methods=['POST'])
def api_create_sampling():
    return create_sampling_route()

@sampling_api_bp.route('/sampling/<pond_id>', methods=['GET'])
def api_list_sampling_for_pond(pond_id):
    return list_sampling_for_pond_route(pond_id)

@sampling_api_bp.route('/sampling/<sampling_id>', methods=['PUT'])
def api_update_sampling(sampling_id):
    return update_sampling_route(sampling_id)

@sampling_api_bp.route('/sampling/<sampling_id>', methods=['DELETE'])
def api_delete_sampling(sampling_id):
    return delete_sampling_route(sampling_id)

