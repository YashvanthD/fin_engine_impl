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
        # recordedBy (and persisted recorded_by) already stores the sampler extracted from the token

        # Ensure we include a type field for sampling
        if dto.extra is None:
            dto.extra = {}
        # only set if caller didn't explicitly set a type
        dto.extra.setdefault('type', 'sampling')

        # Ensure a sampling identifier exists (human-friendly). Accept client-provided sampling_id or generate one.
        # Format: SAMP-YYYYMMDDHHMMSS-<rand4>
        try:
            if not dto.extra.get('sampling_id'):
                from fin_server.utils.time_utils import get_time_date_dt
                import random
                ts = get_time_date_dt(include_time=True).strftime('%Y%m%d%H%M%S')
                suffix = str(random.randint(1000, 9999))
                sid = f"SAMP-{ts}-{suffix}"
                dto.extra['sampling_id'] = sid
        except Exception:
            # never fail creation because of sampling id generation
            current_app.logger.exception('Failed to generate sampling id')

        # Determine total amount: allow manual override (totalAmount), otherwise compute
        total_amount = None
        # Accept either camelCase or snake_case keys
        if 'totalAmount' in data and data.get('totalAmount') not in (None, ''):
            try:
                total_amount = float(data.get('totalAmount'))
            except Exception:
                total_amount = None
        elif 'total_amount' in data and data.get('total_amount') not in (None, ''):
            try:
                total_amount = float(data.get('total_amount'))
            except Exception:
                total_amount = None
        else:
            # compute only if cost and sampleSize are available
            try:
                cost = dto.cost if getattr(dto, 'cost', None) is not None else None
                count = dto.sampleSize if getattr(dto, 'sampleSize', None) is not None else None
                if cost is not None and count is not None:
                    # detect cost unit (default to per kg)
                    cost_unit = data.get('costUnit') or data.get('cost_unit') or data.get('costType') or data.get('cost_type') or 'kg'
                    cost_unit = str(cost_unit).lower()
                    if cost_unit in ('unit', 'per_fish', 'perfish', 'fish', 'count'):
                        total_amount = float(cost) * int(count)
                    else:
                        # per kg: use averageWeight, but enforce minimum 1 kg per fish when under 1kg
                        weight = None
                        if getattr(dto, 'averageWeight', None) is not None:
                            weight = dto.averageWeight
                        else:
                            # allow payload to specify minWeight/min_weight
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
            except Exception:
                total_amount = None

        # Persist the computed or provided total amount so frontend can override later
        if total_amount is not None:
            # round to 2 decimals for currency
            try:
                total_amount = round(float(total_amount), 2)
            except Exception:
                pass
            dto.extra['totalAmount'] = total_amount

        try:
            res = dto.save(repo=repo, collection_name='sampling')
            inserted_id = getattr(res, 'inserted_id', res)
            inserted_id = str(inserted_id) if inserted_id is not None else None
        except Exception:
            sr = repo.get_collection('sampling')
            rr = sr.insert_one(dto.to_db_doc())
            inserted_id = str(rr.inserted_id)
        dto.id = inserted_id
        # Prepare post-processing variables so they're always defined
        extra = dto.extra or {}
        is_buy = False
        buy_count = None
        # If this sampling payload represents a purchase / buying fish, update related entities
        try:
            # Determine buy intent: look for explicit transactionType/transaction_type == 'buy' or buy_count/bought fields
            extra = dto.extra or {}
            # Extract transaction type robustly (accept multiple key names and non-string values)
            tx_val = extra.get('transactionType') or extra.get('transaction_type') or extra.get('transaction')
            if tx_val is None:
                # fall back to general 'type' or 'action' keys
                tx_val = extra.get('type') or extra.get('action')
            if isinstance(tx_val, str):
                tx = tx_val.strip().lower()
            else:
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
            if 'bought' in extra:
                try:
                    buy_count = int(extra.get('bought'))
                except Exception:
                    pass
            # Fallback to sampleSize for count if not explicitly provided
            if buy_count is None and getattr(dto, 'sampleSize', None) is not None:
                try:
                    buy_count = int(dto.sampleSize)
                except Exception:
                    buy_count = None

            is_buy = (tx == 'buy' or tx == 'purchase' or buy_count is not None)
            if is_buy and buy_count and buy_count > 0:
                mr = MongoRepositorySingleton.get_instance()
                # pond update: increment fish_count or stock by buy_count
                try:
                    pond_repo = mr.pond
                    # prefer pond_id key from DTO
                    pond_id = dto.pondId
                    inc_fields = {'fish_count': buy_count}
                    pond_repo.atomic_update_metadata(pond_id, inc_fields=inc_fields)
                except Exception:
                    current_app.logger.exception('Failed to update pond metadata for buy')

                # pond event: record a buy event
                try:
                    pe = mr.pond_event
                    event_doc = {
                        'pond_id': dto.pondId,
                        'event_type': 'buy',
                        'details': {
                            'species': dto.species,
                            'count': buy_count,
                            'cost_unit': extra.get('costUnit') or extra.get('cost_unit'),
                            'total_amount': extra.get('totalAmount') if 'totalAmount' in extra else extra.get('total_amount')
                        },
                        'recorded_by': dto.recordedBy
                    }
                    try:
                        pe.create(event_doc)
                    except Exception:
                        # fallback to direct collection insert
                        mr.get_collection('pond_events').insert_one(event_doc)
                except Exception:
                    current_app.logger.exception('Failed to create pond event for buy')

                # fish repository: increment fish stock for species or create a fish entry
                try:
                    fish_repo = mr.fish
                    # We'll try to find a fish document by species code
                    query = {'species_code': dto.species}
                    existing = fish_repo.find_one(query)
                    if existing:
                        # increment a 'stock' or 'current_stock' field
                        delta_field = 'current_stock'
                        fish_repo.update({'_id': existing.get('_id')}, {delta_field: (existing.get(delta_field, 0) + buy_count)})
                    else:
                        # create a minimal fish document
                        fish_doc = {
                            'species_code': dto.species,
                            'common_name': dto.species,
                            'current_stock': buy_count,
                            'account_key': payload.get('account_key')
                        }
                        try:
                            fish_repo.create(fish_doc)
                        except Exception:
                            mr.get_collection('fish').insert_one(fish_doc)
                except Exception:
                    current_app.logger.exception('Failed to update/create fish record for buy')

                # expenses: insert a purchase expense if total amount present
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
                    elif getattr(dto, 'cost', None) is not None and buy_count is not None:
                        # best-effort compute
                        try:
                            total_amt = float(dto.cost) * float(buy_count)
                        except Exception:
                            total_amt = None
                    if expenses_repo and total_amt is not None:
                        expense_doc = {
                            'pond_id': dto.pondId,
                            'species': dto.species,
                            'category': 'buy',
                            'amount': total_amt,
                            'currency': extra.get('currency') or 'INR',
                            'notes': extra.get('notes'),
                            'recorded_by': dto.recordedBy,
                            'account_key': payload.get('account_key')
                        }
                        try:
                            expenses_repo.create(expense_doc)
                        except Exception:
                            mr.get_collection('expenses').insert_one(expense_doc)
                except Exception:
                    current_app.logger.exception('Failed to insert expense record for buy')
                # Add analytics batch for the purchase (positive count)
                try:
                    from fin_server.repository.fish_analytics_repository import FishAnalyticsRepository
                    fa = FishAnalyticsRepository()
                    # attempt to extract fish_age from extra or dto
                    fish_age = extra.get('fish_age_in_month') if extra.get('fish_age_in_month') is not None else extra.get('fish_age') if extra.get('fish_age') is not None else None
                    event_id = f"{payload.get('account_key')}-{dto.species}-{dto.pondId}-{inserted_id}"
                    try:
                        fish_weight = getattr(dto, 'averageWeight', None)
                        fa.add_batch(dto.species, int(buy_count), int(fish_age) if fish_age is not None else 0, account_key=payload.get('account_key'), event_id=event_id, fish_weight=fish_weight if (fish_weight is not None) else None, pond_id=dto.pondId)
                    except Exception:
                        # best-effort: ensure call doesn't break flow
                        current_app.logger.exception('Failed to add analytics batch for buy')
                except Exception:
                    current_app.logger.exception('FishAnalyticsRepository not available for buy analytics')

                # Record a fish_activity entry for the buy (best-effort)
                try:
                    from fin_server.repository.fish_activity_repository import FishActivityRepository
                    far = FishActivityRepository()
                    activity_doc = {
                        'account_key': payload.get('account_key'),
                        'pond_id': dto.pondId,
                        'fish_id': dto.species,
                        'event_type': 'buy',
                        'count': buy_count,
                        'details': extra.get('details') or {},
                        'created_at': None,
                        'user_key': dto.recordedBy
                    }
                    try:
                        far.create(activity_doc)
                    except Exception:
                        # fallback to collection insert
                        MongoRepositorySingleton.get_instance().get_collection('fish_activity').insert_one(activity_doc)
                except Exception:
                    current_app.logger.exception('Failed to record fish_activity for buy')
                # Update pond.current_stock: increment if species exists otherwise push new stock record
                try:
                    from fin_server.utils.time_utils import get_time_date_dt
                    ponds_coll = MongoRepositorySingleton.get_instance().get_collection('ponds')
                    # Try increment existing stock entry
                    try:
                        res = ponds_coll.update_one({'pond_id': dto.pondId, 'current_stock.species': dto.species},
                                                   {'$inc': {'current_stock.$.quantity': int(buy_count)},
                                                    '$set': {'current_stock.$.average_weight': getattr(dto, 'averageWeight', None)}})
                        if not res.matched_count:
                            stock_doc = {
                                'stock_id': dto.extra.get('sampling_id') or inserted_id,
                                'species': dto.species,
                                'quantity': int(buy_count),
                                'average_weight': getattr(dto, 'averageWeight', None),
                                'stocking_date': get_time_date_dt(include_time=True)
                            }
                            ponds_coll.update_one({'pond_id': dto.pondId}, {'$push': {'current_stock': stock_doc}})
                    except Exception:
                        # best-effort fallback: try to read and update manually
                        try:
                            pond = ponds_coll.find_one({'pond_id': dto.pondId})
                            if pond:
                                updated = False
                                cs = pond.get('current_stock') or []
                                for s in cs:
                                    if s.get('species') == dto.species:
                                        try:
                                            s['quantity'] = int(s.get('quantity', 0) or 0) + int(buy_count)
                                        except Exception:
                                            s['quantity'] = (s.get('quantity') or 0) + buy_count
                                        updated = True
                                        break
                                if not updated:
                                    cs.append({'stock_id': dto.extra.get('sampling_id') or inserted_id, 'species': dto.species, 'quantity': int(buy_count), 'average_weight': getattr(dto, 'averageWeight', None), 'stocking_date': get_time_date_dt(include_time=True)})
                                ponds_coll.update_one({'pond_id': dto.pondId}, {'$set': {'current_stock': cs}})
                        except Exception:
                            current_app.logger.exception('Failed to update pond current_stock for buy')
                except Exception:
                    current_app.logger.exception('Unexpected error updating pond current_stock for buy')
        except Exception:
            current_app.logger.exception('Failed post-sampling buy handling')
        # If not a buy, handle sampling-specific post-processing: pond_event and fish_activity, fish_mapping
        try:
            if not is_buy:
                try:
                    mr = MongoRepositorySingleton.get_instance()
                    # Ensure mapping exists
                    try:
                        fish_mapping = mr.fish_mapping
                        try:
                            fish_mapping.add_fish_to_account(payload.get('account_key'), dto.species)
                        except Exception:
                            # fallback: update mapping collection directly
                            mapping_coll = mr.get_collection('fish_mapping')
                            mapping_coll.update_one({'account_key': payload.get('account_key')}, {'$addToSet': {'fish_ids': dto.species}}, upsert=True)
                    except Exception:
                        current_app.logger.exception('Failed to ensure fish mapping during sampling')

                    # Create a pond_event record for sampling (best-effort)
                    try:
                        pe = mr.pond_event
                        event_doc = {
                            'pond_id': dto.pondId,
                            'event_type': 'sample',
                            'details': extra.get('details', {}),
                            'samples': data.get('samples') if isinstance(data.get('samples'), list) else None,
                            'count': int(dto.sampleSize) if getattr(dto, 'sampleSize', None) is not None else None,
                            'created_at': None,
                            'user_key': dto.recordedBy
                        }
                        try:
                            pe.create(event_doc)
                        except Exception:
                            mr.get_collection('pond_events').insert_one(event_doc)
                    except Exception:
                        current_app.logger.exception('Failed to create pond_event for sampling')

                    # Record fish_activity for sampling (samples array if present)
                    try:
                        from fin_server.repository.fish_activity_repository import FishActivityRepository
                        far = FishActivityRepository()
                        activity_doc = {
                            'account_key': payload.get('account_key'),
                            'pond_id': dto.pondId,
                            'fish_id': dto.species,
                            'event_type': 'sample',
                            'count': int(dto.sampleSize) if getattr(dto, 'sampleSize', None) is not None else None,
                            'user_key': dto.recordedBy,
                            'details': extra.get('details', {}),
                            'samples': data.get('samples') if isinstance(data.get('samples'), list) else None
                        }
                        try:
                            far.create(activity_doc)
                        except Exception:
                            mr.get_collection('fish_activity').insert_one(activity_doc)
                    except Exception:
                        current_app.logger.exception('Failed to record fish_activity for sampling')
                    # Decrement current_stock in pond for sampled species and remove depleted entries
                    try:
                        ponds_coll = mr.get_collection('ponds')
                        sample_count = int(dto.sampleSize) if getattr(dto, 'sampleSize', None) is not None else 0
                        if sample_count:
                            try:
                                res = ponds_coll.update_one({'pond_id': dto.pondId, 'current_stock.species': dto.species}, {'$inc': {'current_stock.$.quantity': -sample_count}})
                            except Exception:
                                # fallback: manual read-modify-write
                                pond = ponds_coll.find_one({'pond_id': dto.pondId})
                                if pond:
                                    cs = pond.get('current_stock') or []
                                    changed = False
                                    for s in cs:
                                        if s.get('species') == dto.species:
                                            try:
                                                s['quantity'] = int(s.get('quantity', 0) or 0) - sample_count
                                            except Exception:
                                                s['quantity'] = (s.get('quantity') or 0) - sample_count
                                            changed = True
                                            break
                                    if changed:
                                        # remove depleted entries
                                        cs = [s for s in cs if (s.get('quantity') or 0) > 0]
                                        ponds_coll.update_one({'pond_id': dto.pondId}, {'$set': {'current_stock': cs}})
                            # After decrement attempt, ensure no negative qty entries
                            try:
                                ponds_coll.update_one({'pond_id': dto.pondId}, {'$pull': {'current_stock': {'quantity': {'$lte': 0}}}})
                            except Exception:
                                pass
                    except Exception:
                        current_app.logger.exception('Failed to decrement pond current_stock for sampling')
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
