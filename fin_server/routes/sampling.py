from flask import Blueprint, request, current_app

from fin_server.dto.growth_dto import GrowthRecordDTO
from fin_server.exception.UnauthorizedError import UnauthorizedError
from fin_server.repository.fish.fish_activity_repository import FishActivityRepository
from fin_server.repository.fish.fish_analytics_repository import FishAnalyticsRepository
from fin_server.repository.fish.stock_repository import StockRepository
from fin_server.repository.mongo_helper import get_collection
from fin_server.routes.fish import fish_analytics_repo
from fin_server.routes.pond_event import fish_activity_repo
from fin_server.security.authentication import get_auth_payload
from fin_server.utils.generator import generate_sampling_id
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc, parse_iso_or_epoch
from fin_server.utils.threading_util import submit_task
from fin_server.utils.validation import compute_total_amount_from_payload

sampling_bp = Blueprint('sampling', __name__, url_prefix='/sampling')

sampling_repo = get_collection('sampling')
pond_repo = get_collection('pond')
fish_repo = get_collection('fish')
expenses_repo = get_collection('expenses')
pond_event_repo = get_collection('pond_event')

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

        # Best-effort post-processing operations
        # 1) Buy handling
        if is_buy and buy_count and buy_count > 0:
            # pond metadata increment
            pond_repo.atomic_update_metadata(dto.pondId, inc_fields={'fish_count': buy_count})

            # pond event
            event_doc = {
                'pond_id': dto.pondId,
                'event_type': 'buy',
                'details': {'species': dto.species, 'count': buy_count, 'cost_unit': extra.get('costUnit') or extra.get('cost_unit'), 'total_amount': extra.get('totalAmount') or extra.get('total_amount')},
                'recorded_by': dto.recordedBy
            }
            pond_event_repo.create(event_doc)

            # fish repo update/create
            existing = fish_repo.find_one({'species_code': dto.species})
            if existing:
                fish_repo.update({'_id': existing.get('_id')}, {'current_stock': (existing.get('current_stock', 0) or 0) + buy_count})
            else:
                fish_doc = {'_id': dto.species, 'species_code': dto.species, 'common_name': dto.species, 'current_stock': buy_count, 'account_key': payload.get('account_key')}
                fish_repo.create(fish_doc)

            # expenses
            total_amt = None
            if 'totalAmount' in extra:
                total_amt = float(extra.get('totalAmount'))
            elif getattr(dto, 'cost', None) is not None:
                total_amt = float(dto.cost) * float(buy_count)
            if expenses_repo and total_amt is not None:
                expense_doc = {
                    'pond_id': dto.pondId,
                    'amount': total_amt,
                    'currency': extra.get('currency') or 'INR',
                    'payment_method': extra.get('payment_method') or 'cash',
                    'notes': extra.get('notes') or getattr(dto, 'notes', None),
                    'recorded_by': dto.recordedBy,
                    'account_key': payload.get('account_key'),
                    # domain metadata
                    'category': extra.get('category') or 'asset',
                    'action': extra.get('action') or 'buy',
                    'type': extra.get('type') or 'fish'
                }
                # strip none
                expense_doc = {k: v for k, v in expense_doc.items() if v is not None}
                # Use the ExpensesRepository API (create_expense). Fail fast if not available.
                if not hasattr(expenses_repo, 'create_expense'):
                    # This is a strict change: require the higher-level expenses API
                    raise RuntimeError('Expenses repository missing create_expense API')
                expenses_repo.create_expense(expense_doc)

            # analytics batch (positive)
            fish_age = extra.get('fish_age_in_month') or extra.get('fish_age')
            fish_weight = getattr(dto, 'averageWeight', None)
            event_id = f"{payload.get('account_key')}-{dto.species}-{dto.pondId}-{dto.id}"
            fish_analytics_repo.add_batch(dto.species, int(buy_count), int(fish_age) if fish_age is not None else 0, account_key=payload.get('account_key'), event_id=event_id, fish_weight=fish_weight if fish_weight is not None else None, pond_id=dto.pondId)

            # fish_activity
            activity_doc = {'account_key': payload.get('account_key'), 'pond_id': dto.pondId, 'fish_id': dto.species, 'event_type': 'buy', 'count': buy_count, 'details': extra.get('details') or {}, 'user_key': dto.recordedBy}
            fish_activity_repo.create(activity_doc)

            # update pond.current_stock using reusable StockRepository asynchronously
            def _run_stock_update(account_key, pond_id, species, count, average_weight, sampling_id_val, recorded_by_val, expense_amount_val):
                sr = StockRepository()
                ok_inner = sr.add_stock_transactional(account_key, pond_id, species, count, average_weight=average_weight, sampling_id=sampling_id_val, recorded_by=recorded_by_val, expense_amount=expense_amount_val, timeout_seconds=3)
                if not ok_inner:
                    sr.add_stock_to_pond(account_key, pond_id, species, count, average_weight=average_weight, sampling_id=sampling_id_val, recorded_by=recorded_by_val, create_event=False, create_activity=False, create_analytics=False, create_expense=True, expense_amount=expense_amount_val)

            sampling_id_val = dto.extra.get('sampling_id') or dto.id
            submit_task(_run_stock_update, payload.get('account_key'), dto.pondId, dto.species, buy_count, getattr(dto, 'averageWeight', None), sampling_id_val, dto.recordedBy, total_amt)

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

        # handle totalCount / total_count -> total_count
        if 'totalCount' in data:
            try:
                update_fields['total_count'] = int(float(data.get('totalCount')))
            except Exception:
                update_fields['total_count'] = data.get('totalCount')
        elif 'total_count' in data:
            try:
                update_fields['total_count'] = int(float(data.get('total_count')))
            except Exception:
                update_fields['total_count'] = data.get('total_count')

        # Allow updating extra fields passed inside an 'extra' object
        if isinstance(data.get('extra'), dict):
            for ek, ev in data.get('extra').items():
                update_fields[ek] = ev

        # Remove None-valued fields from updates (do not store nulls)
        update_fields = {k: v for k, v in update_fields.items() if v is not None}
        if not update_fields:
            return respond_error('No updatable fields provided', status=400)

        # Apply update
        try:
            res = sampling_repo.update_one({'_id': existing.get('_id')}, {'$set': update_fields})
        except Exception:
            return respond_error('Failed to update sampling record', status=500)

        updated = sampling_repo.find_one({'_id': existing.get('_id')})
        # Normalize and try to use DTO for response
        ro = normalize_doc(updated)
        try:
            dto = GrowthRecordDTO.from_doc(ro)
            return respond_success(dto.to_dict())
        except Exception:
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
