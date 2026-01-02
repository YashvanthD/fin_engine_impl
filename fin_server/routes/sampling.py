from flask import Blueprint, request, current_app
from fin_server.repository.mongo_helper import MongoRepositorySingleton
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc, parse_iso_or_epoch
from fin_server.security.authentication import get_auth_payload
from fin_server.exception.UnauthorizedError import UnauthorizedError
from fin_server.dto.growth_dto import GrowthRecordDTO

sampling_bp = Blueprint('sampling', __name__, url_prefix='/sampling')
repo = MongoRepositorySingleton.get_instance()

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
        # Normalize extra
        dto.extra = dto.extra or {}
        dto.extra.setdefault('type', 'sampling')

        # Ensure sampling_id exists
        try:
            if not dto.extra.get('sampling_id'):
                from fin_server.utils.time_utils import get_time_date_dt
                import random
                ts = get_time_date_dt(include_time=True).strftime('%Y%m%d%H%M%S')
                dto.extra['sampling_id'] = f"SAMP-{ts}-{random.randint(1000,9999)}"
        except Exception:
            current_app.logger.exception('Failed to generate sampling id')

        # Compute total amount if not provided
        total_amount = None
        try:
            if 'totalAmount' in data and data.get('totalAmount') not in (None, ''):
                total_amount = float(data.get('totalAmount'))
            elif 'total_amount' in data and data.get('total_amount') not in (None, ''):
                total_amount = float(data.get('total_amount'))
            else:
                cost = getattr(dto, 'cost', None)
                count = getattr(dto, 'sampleSize', None)
                if cost is not None and count is not None:
                    cost_unit = data.get('costUnit') or data.get('cost_unit') or data.get('costType') or data.get('cost_type') or 'kg'
                    cost_unit = str(cost_unit).lower()
                    if cost_unit in ('unit', 'per_fish', 'perfish', 'fish', 'count'):
                        total_amount = float(cost) * int(count)
                    else:
                        weight = getattr(dto, 'averageWeight', None)
                        if weight is None:
                            mw = data.get('minWeight') or data.get('min_weight')
                            try:
                                weight = float(mw) if mw not in (None, '') else None
                            except Exception:
                                weight = None
                        if weight is None:
                            weight = 1.0
                        try:
                            weight = float(weight)
                        except Exception:
                            weight = 1.0
                        if weight < 1.0:
                            weight = 1.0
                        total_amount = float(cost) * float(weight) * int(count)
                # round
            if total_amount is not None:
                try:
                    dto.extra['totalAmount'] = round(float(total_amount), 2)
                except Exception:
                    dto.extra['totalAmount'] = total_amount
        except Exception:
            current_app.logger.exception('Failed to compute total amount')

        # Persist sampling
        try:
            res = dto.save(repo=repo, collection_name='sampling')
            inserted_id = getattr(res, 'inserted_id', res)
            inserted_id = str(inserted_id) if inserted_id is not None else None
        except Exception:
            sr = repo.get_collection('sampling')
            rr = sr.insert_one(dto.to_db_doc())
            inserted_id = str(rr.inserted_id)
        dto.id = inserted_id

        # Detect buy vs sample
        extra = dto.extra or {}
        tx_val = extra.get('transactionType') or extra.get('transaction_type') or extra.get('transaction') or extra.get('type') or extra.get('action')
        try:
            tx = str(tx_val).strip().lower() if tx_val is not None else ''
        except Exception:
            tx = ''
        buy_count = None
        if 'buy_count' in extra:
            try:
                buy_count = int(extra.get('buy_count'))
            except Exception:
                buy_count = None
        if 'bought' in extra and buy_count is None:
            try:
                buy_count = int(extra.get('bought'))
            except Exception:
                buy_count = None
        if buy_count is None and getattr(dto, 'sampleSize', None) is not None and tx in ('buy', 'purchase'):
            try:
                buy_count = int(dto.sampleSize)
            except Exception:
                buy_count = None
        is_buy = (tx in ('buy', 'purchase')) or (buy_count is not None and tx == '')

        # Best-effort post-processing operations
        mr = MongoRepositorySingleton.get_instance()
        # 1) Buy handling
        if is_buy and buy_count and buy_count > 0:
            try:
                # pond metadata increment
                try:
                    pond_repo = mr.pond
                    pond_repo.atomic_update_metadata(dto.pondId, inc_fields={'fish_count': buy_count})
                except Exception:
                    current_app.logger.exception('Failed to atomic update pond metadata for buy')

                # pond event
                try:
                    pe = mr.pond_event
                    event_doc = {'pond_id': dto.pondId, 'event_type': 'buy', 'details': {'species': dto.species, 'count': buy_count, 'cost_unit': extra.get('costUnit') or extra.get('cost_unit'), 'total_amount': extra.get('totalAmount') or extra.get('total_amount')}, 'recorded_by': dto.recordedBy}
                    try:
                        pe.create(event_doc)
                    except Exception:
                        mr.get_collection('pond_events').insert_one(event_doc)
                except Exception:
                    current_app.logger.exception('Failed to create pond_event for buy')

                # fish repo update/create
                try:
                    fish_repo = mr.fish
                    existing = fish_repo.find_one({'species_code': dto.species})
                    if existing:
                        try:
                            fish_repo.update({'_id': existing.get('_id')}, {'current_stock': (existing.get('current_stock', 0) or 0) + buy_count})
                        except Exception:
                            # best-effort direct update
                            mr.get_collection('fish').update_one({'_id': existing.get('_id')}, {'$inc': {'current_stock': buy_count}})
                    else:
                        fish_doc = {'_id': dto.species, 'species_code': dto.species, 'common_name': dto.species, 'current_stock': buy_count, 'account_key': payload.get('account_key')}
                        try:
                            fish_repo.create(fish_doc)
                        except Exception:
                            mr.get_collection('fish').insert_one(fish_doc)
                except Exception:
                    current_app.logger.exception('Failed to update/create fish record for buy')

                # expenses
                try:
                    expenses_repo = mr.expenses
                    total_amt = None
                    if 'totalAmount' in extra:
                        try:
                            total_amt = float(extra.get('totalAmount'))
                        except Exception:
                            total_amt = None
                    elif 'total_amount' in extra:
                        try:
                            total_amt = float(extra.get('total_amount'))
                        except Exception:
                            total_amt = None
                    elif getattr(dto, 'cost', None) is not None:
                        try:
                            total_amt = float(dto.cost) * float(buy_count)
                        except Exception:
                            total_amt = None
                    if expenses_repo and total_amt is not None:
                        expense_doc = {'pond_id': dto.pondId, 'species': dto.species, 'category': 'buy', 'amount': total_amt, 'currency': extra.get('currency') or 'INR', 'notes': extra.get('notes'), 'recorded_by': dto.recordedBy, 'account_key': payload.get('account_key')}
                        try:
                            expenses_repo.create(expense_doc)
                        except Exception:
                            mr.get_collection('expenses').insert_one(expense_doc)
                except Exception:
                    current_app.logger.exception('Failed to insert expense record for buy')

                # analytics batch (positive)
                try:
                    from fin_server.repository.fish_analytics_repository import FishAnalyticsRepository
                    fa = FishAnalyticsRepository()
                    fish_age = extra.get('fish_age_in_month') or extra.get('fish_age')
                    fish_weight = getattr(dto, 'averageWeight', None)
                    event_id = f"{payload.get('account_key')}-{dto.species}-{dto.pondId}-{inserted_id}"
                    fa.add_batch(dto.species, int(buy_count), int(fish_age) if fish_age is not None else 0, account_key=payload.get('account_key'), event_id=event_id, fish_weight=fish_weight if fish_weight is not None else None, pond_id=dto.pondId)
                except Exception:
                    current_app.logger.exception('Failed to add analytics batch for buy')

                # fish_activity
                try:
                    from fin_server.repository.fish_activity_repository import FishActivityRepository
                    far = FishActivityRepository()
                    activity_doc = {'account_key': payload.get('account_key'), 'pond_id': dto.pondId, 'fish_id': dto.species, 'event_type': 'buy', 'count': buy_count, 'details': extra.get('details') or {}, 'user_key': dto.recordedBy}
                    try:
                        far.create(activity_doc)
                    except Exception:
                        mr.get_collection('fish_activity').insert_one(activity_doc)
                except Exception:
                    current_app.logger.exception('Failed to record fish_activity for buy')

                # update pond.current_stock using reusable StockRepository
                try:
                    from fin_server.repository.stock_repository import StockRepository
                    sr = StockRepository()
                    sr.add_stock_to_pond(payload.get('account_key'), dto.pondId, dto.species, buy_count, average_weight=getattr(dto, 'averageWeight', None), sampling_id=dto.extra.get('sampling_id') or inserted_id, recorded_by=dto.recordedBy, create_event=False, create_activity=False, create_analytics=False, create_expense=False)
                except Exception:
                    current_app.logger.exception('Failed to update pond current_stock for buy (via StockRepository)')

            except Exception:
                current_app.logger.exception('Unexpected error during buy post-processing')

        else:
            # 2) Sampling (non-buy) handling
            try:
                try:
                    fish_mapping = mr.fish_mapping
                    try:
                        fish_mapping.add_fish_to_account(payload.get('account_key'), dto.species)
                    except Exception:
                        mr.get_collection('fish_mapping').update_one({'account_key': payload.get('account_key')}, {'$addToSet': {'fish_ids': dto.species}}, upsert=True)
                except Exception:
                    current_app.logger.exception('Failed to ensure fish mapping during sampling')

                # pond_event for sample
                try:
                    pe = mr.pond_event
                    event_doc = {'pond_id': dto.pondId, 'event_type': 'sample', 'details': extra.get('details', {}), 'samples': data.get('samples') if isinstance(data.get('samples'), list) else None, 'count': int(dto.sampleSize) if getattr(dto, 'sampleSize', None) is not None else None, 'user_key': dto.recordedBy}
                    try:
                        pe.create(event_doc)
                    except Exception:
                        mr.get_collection('pond_events').insert_one(event_doc)
                except Exception:
                    current_app.logger.exception('Failed to create pond_event for sampling')

                # fish_activity for sample
                try:
                    from fin_server.repository.fish_activity_repository import FishActivityRepository
                    far = FishActivityRepository()
                    activity_doc = {'account_key': payload.get('account_key'), 'pond_id': dto.pondId, 'fish_id': dto.species, 'event_type': 'sample', 'count': int(dto.sampleSize) if getattr(dto, 'sampleSize', None) is not None else None, 'user_key': dto.recordedBy, 'details': extra.get('details', {}), 'samples': data.get('samples') if isinstance(data.get('samples'), list) else None}
                    try:
                        far.create(activity_doc)
                    except Exception:
                        mr.get_collection('fish_activity').insert_one(activity_doc)
                except Exception:
                    current_app.logger.exception('Failed to record fish_activity for sampling')

                # decrement pond.current_stock using StockRepository
                try:
                    from fin_server.repository.stock_repository import StockRepository
                    sr = StockRepository()
                    sr.remove_stock_from_pond(payload.get('account_key'), dto.pondId, dto.species, int(dto.sampleSize) if getattr(dto, 'sampleSize', None) is not None else 0, recorded_by=dto.recordedBy, create_event=False, create_activity=False, create_analytics=False)
                except Exception:
                    current_app.logger.exception('Failed to decrement pond current_stock for sampling (via StockRepository)')

                # analytics negative batch for sample
                try:
                    from fin_server.repository.fish_analytics_repository import FishAnalyticsRepository
                    fa = FishAnalyticsRepository()
                    fish_age = extra.get('fish_age_in_month') or extra.get('fish_age')
                    sample_count = int(dto.sampleSize) if getattr(dto, 'sampleSize', None) is not None else 0
                    if sample_count:
                        event_id = f"{payload.get('account_key')}-{dto.species}-sample-{inserted_id}"
                        fa.add_batch(dto.species, -int(sample_count), int(fish_age) if fish_age is not None else 0, account_key=payload.get('account_key'), event_id=event_id, fish_weight=getattr(dto, 'averageWeight', None), pond_id=dto.pondId)
                except Exception:
                    current_app.logger.exception('Failed to add analytics batch for sampling')

            except Exception:
                current_app.logger.exception('Unexpected error during sampling post-processing')

        return respond_success(dto.to_dict(), status=201)
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        current_app.logger.exception('Error in create_sampling_route')
        return respond_error('Server error', status=500)

@sampling_bp.route('/<pond_id>', methods=['GET'])
def list_sampling_for_pond_route(pond_id):
    try:
        sr = repo.get_collection('sampling')
        recs = list(sr.find({'pondId': pond_id}).sort('created_at', -1))
        out = []
        for r in recs:
            ro = normalize_doc(r)
            try:
                dto = GrowthRecordDTO.from_doc(ro)
                out.append(dto.to_dict())
            except Exception:
                ro['_id'] = str(ro.get('_id'))
                ro['id'] = ro['_id']
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

        sr = repo.get_collection('sampling')
        cursor = sr.find(q).sort([('sampling_date', -1), ('created_at', -1)]).limit(limit)
        recs = list(cursor)
        out = []
        for r in recs:
            ro = normalize_doc(r)
            try:
                dto = GrowthRecordDTO.from_doc(ro)
                out.append(dto.to_dict())
            except Exception:
                ro['_id'] = str(ro.get('_id'))
                ro['id'] = ro['_id']
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
        coll = repo.get_collection('sampling')

        # Try to resolve sampling by _id (ObjectId) or by sampling_id field
        query = None
        try:
            from bson import ObjectId
            query = {'_id': ObjectId(sampling_id)}
        except Exception:
            # not an ObjectId
            query = {'sampling_id': sampling_id}

        existing = coll.find_one(query)
        if not existing:
            # Try alternative: direct sampling_id match
            existing = coll.find_one({'sampling_id': sampling_id})
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
            'notes': 'notes'
        }

        update_fields = {}
        # normalize incoming keys presence and set corresponding db fields
        for k, dbk in key_map.items():
            if k in data:
                update_fields[dbk] = data.get(k)

        # handle totalAmount / total_amount -> total_cost
        if 'totalAmount' in data:
            try:
                update_fields['total_cost'] = float(data.get('totalAmount'))
            except Exception:
                update_fields['total_cost'] = data.get('totalAmount')
        elif 'total_amount' in data:
            try:
                update_fields['total_cost'] = float(data.get('total_amount'))
            except Exception:
                update_fields['total_cost'] = data.get('total_amount')

        # handle costUnit / cost_unit
        if 'costUnit' in data:
            update_fields['cost_unit'] = data.get('costUnit')
        elif 'cost_unit' in data:
            update_fields['cost_unit'] = data.get('cost_unit')

        # Allow updating extra fields passed inside an 'extra' object
        if isinstance(data.get('extra'), dict):
            for ek, ev in data.get('extra').items():
                update_fields[ek] = ev

        if not update_fields:
            return respond_error('No updatable fields provided', status=400)

        # Apply update
        try:
            res = coll.update_one({'_id': existing.get('_id')}, {'$set': update_fields})
        except Exception:
            return respond_error('Failed to update sampling record', status=500)

        updated = coll.find_one({'_id': existing.get('_id')})
        # Normalize and try to use DTO for response
        ro = normalize_doc(updated)
        try:
            dto = GrowthRecordDTO.from_doc(ro)
            return respond_success(dto.to_dict())
        except Exception:
            ro['_id'] = str(ro.get('_id'))
            ro['id'] = ro['_id']
            return respond_success(ro)
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        current_app.logger.exception('Error in update_sampling_route')
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
