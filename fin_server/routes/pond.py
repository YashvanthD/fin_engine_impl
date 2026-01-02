from flask import Blueprint, request, current_app
from datetime import datetime
import zoneinfo

from fin_server.exception.UnauthorizedError import UnauthorizedError
from fin_server.repository.pond_repository import PondRepository
from fin_server.security.authentication import get_auth_payload
from fin_server.utils.helpers import get_request_payload, parse_pagination
from fin_server.utils.helpers import normalize_doc, respond_success, respond_error
from fin_server.utils.time_utils import get_time_date_dt
from fin_server.dto.pond_dto import PondDTO

pond_bp = Blueprint('pond', __name__, url_prefix='/pond')
IST_TZ = zoneinfo.ZoneInfo('Asia/Kolkata')
pond_repository = PondRepository()

@pond_bp.route('', methods=['OPTIONS'])
def pond_options_root():
    """Handle CORS preflight for /pond (no trailing slash).

    This prevents Flask from issuing a 308 redirect from /pond to /pond/,
    which would otherwise cause the browser's CORS preflight to fail.
    """
    resp = current_app.make_default_options_response()
    return resp

@pond_bp.route('', methods=['GET'])
def list_ponds_no_slash():
    """Alias for listing ponds when client calls /pond without trailing slash.

    Delegates to the canonical /pond/ route implementation to avoid
    308 redirects that interfere with CORS preflight.
    """
    return list_ponds()

def pond_to_dict(pond):
    if not pond:
        return None
    pond = dict(pond)
    pond['id'] = str(pond.pop('_id')) if '_id' in pond else None
    if 'created_at' in pond and hasattr(pond['created_at'], 'isoformat'):
        pond['created_at'] = pond['created_at'].isoformat()
    if 'updated_at' in pond and hasattr(pond['updated_at'], 'isoformat'):
        pond['updated_at'] = pond['updated_at'].isoformat()
    return pond

def get_next_pond_number(account_key):
    """
    Returns the next available pond number for the given account_key (auto-increment).
    Looks for pond_ids like <account_key>-<number> and returns next number.
    """
    import re
    ponds = pond_repository.find({'pond_id': {'$regex': f'^{account_key}-\\d+$'}})
    max_num = 0
    for pond in ponds:
        match = re.match(rf'^{re.escape(account_key)}-(\d+)$', pond.get('pond_id', ''))
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num
    return max_num + 1

@pond_bp.route('/create', methods=['POST'])
def create_pond_entity():
    current_app.logger.info('POST /pond/create called')
    try:
        payload = get_auth_payload(request)
        data = request.get_json(force=True)
        account_key = payload.get('account_key')
        data.pop('account_key', None)
        data['created_at'] = get_time_date_dt(include_time=True)
        # Generate pond_id if not provided, using auto-increment
        pond_id = data.get('pond_id')
        if not pond_id:
            next_num = get_next_pond_number(account_key)
            pond_id = f"{account_key}-{next_num:03d}"
            data['pond_id'] = pond_id
        # Check for duplicate pond_id
        existing = pond_repository.find_one({'pond_id': pond_id})
        if existing:
            return respond_error('Pond with this pond_id already exists.', status=409)
        # Insert pond entity (ensure account_key is saved)
        pond_entity = data.copy()
        pond_entity['_id'] = pond_id
        pond_entity['account_key'] = account_key
        # Persist using DTO save helper when possible
        try:
            pdto = PondDTO.from_request(pond_entity)
            res = pdto.save(repo=pond_repository, collection_name='ponds', upsert=True)
            created = pond_repository.find_one({'pond_id': pond_id})
            try:
                return respond_success(PondDTO.from_doc(created).to_dict(), status=201)
            except Exception:
                return respond_success(created, status=201)
        except Exception:
            pond_repository.create(pond_entity)
            created = pond_repository.find_one({'pond_id': pond_id})
            return respond_success(pond_to_dict(created), status=201)
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception(f'Exception in create_pond_entity: {e}')
        return respond_error('Server error', status=500)

@pond_bp.route('/update/<pond_id>', methods=['PUT'])
def update_pond_entity(pond_id):
    current_app.logger.info(f'PUT /pond/update/{pond_id} called')
    try:
        payload = get_auth_payload(request)
        data = request.get_json(force=True)
        # Only allow updating certain fields (not _id/account_key)
        update_fields = {k: v for k, v in data.items() if k not in ['_id', 'account_key', 'pond_id']}
        if not update_fields:
            return respond_error('No updatable fields provided.', status=400)
        account_key = payload.get('account_key')
        result = pond_repository.update({'pond_id': pond_id, 'account_key': account_key}, update_fields)
        if not result or not getattr(result, 'modified_count', 0):
            return respond_error('Pond not found or nothing updated.', status=404)
        updated = pond_repository.find_one({'pond_id': pond_id})
        return respond_success(updated)
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception(f'Exception in update_pond_entity: {e}')
        return respond_error('Server error', status=500)

@pond_bp.route('/<pond_id>', methods=['GET'])
def get_pond(pond_id):
    current_app.logger.debug('GET pond/%s called', pond_id)
    try:
        payload = get_auth_payload(request)

        # enforce account scoping
        account_key = payload.get('account_key')
        pond = pond_repository.find_one({'pond_id': pond_id, 'account_key': account_key})
        if not pond:
            return respond_error('Pond not found', status=404)
        try:
            pond_dto = PondDTO.from_doc(pond)
            return respond_success(pond_dto.to_dict())
        except Exception:
            return respond_success(pond_to_dict(pond))
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        return respond_error('Server error', status=500)

@pond_bp.route('/<pond_id>', methods=['PUT'])
def update_pond(pond_id):
    current_app.logger.debug('PUT /pond/%s called', pond_id)
    try:
        payload = get_auth_payload(request)
        data = request.get_json(force=True)
        account_key = payload.get('account_key')
        result = pond_repository.update({'pond_id': pond_id, 'account_key': account_key}, data)
        if not result or not getattr(result, 'modified_count', 0):
            return respond_error('Pond not found or nothing updated.', status=404)
        updated = pond_repository.find_one({'pond_id': pond_id})
        return respond_success(updated)
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        return respond_error('Server error', status=500)

@pond_bp.route('/<pond_id>', methods=['DELETE'])
def delete_pond(pond_id):
    current_app.logger.debug('DELETE /pond/%s called', pond_id)
    try:
        payload = get_auth_payload(request)
        account_key = payload.get('account_key')
        result = pond_repository.delete({'pond_id': pond_id, 'account_key': account_key})
        if not result or not getattr(result, 'deleted_count', 0):
            return respond_error('Pond not found', status=404)
        return respond_success({'deleted': True})
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        return respond_error('Server error', status=500)

@pond_bp.route('/', methods=['GET'])
def list_ponds():
    """Simple pond list for legacy UI, delegating to api_list_ponds."""
    current_app.logger.debug('GET /pond/ called')
    # Reuse the canonical API helper for listing ponds
    api_resp = api_list_ponds()
    # api_resp is a Flask response tuple from respond_success/respond_error
    resp_obj, status = api_resp
    if status != 200:
        return resp_obj, status
    body = resp_obj.get_json() or {}
    # api_list_ponds returns { success: True, data: <list|dict>, ... }
    data = body.get('data') or body.get('ponds') or {}
    # data may be a list (the typical API payload) or a dict containing nested keys
    if isinstance(data, list):
        ponds = data
    elif isinstance(data, dict):
        ponds = data.get('data') or data.get('ponds') or []
    else:
        ponds = []
    return respond_success({'ponds': ponds})


# GET fish options (for dropdown) for a pond - list fish entities mapped to the account
@pond_bp.route('/<pond_id>/fish_options', methods=['GET'])
def pond_fish_options(pond_id):
    try:
        payload = get_auth_payload(request)
        account_key = payload.get('account_key')
        # find mapped fish ids
        from fin_server.repository.mongo_helper import MongoRepositorySingleton
        fish_mapping = MongoRepositorySingleton.get_instance().fish_mapping
        mapping = fish_mapping.find_one({'account_key': account_key})
        fish_ids = mapping.get('fish_ids', []) if mapping else []
        # return basic fish entities
        from fin_server.repository.fish_repository import FishRepository
        fr = FishRepository()
        fish_list = fr.find({'_id': {'$in': fish_ids}}) if fish_ids else []
        # transform to simple dropdown format
        options = [{'id': f['_id'], 'species_code': f.get('species_code'), 'common_name': f.get('common_name')} for f in fish_list]
        return respond_success({'pondId': pond_id, 'options': options})
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception(f'Exception in pond_fish_options: {e}')
        return respond_error('Server error', status=500)


# GET /pond/<pond_id>/activity - paginated list of fish_activity (samples)
@pond_bp.route('/<pond_id>/activity', methods=['GET'])
def pond_activity(pond_id):
    try:
        payload = get_auth_payload(request)
        account_key = payload.get('account_key')
        fish_id = request.args.get('fish_id')
        limit = int(request.args.get('limit', 50))
        skip = int(request.args.get('skip', 0))
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        from fin_server.repository.fish_activity_repository import FishActivityRepository
        repo = FishActivityRepository()

        query = {'pond_id': pond_id}
        if fish_id:
            query['fish_id'] = fish_id
        # date filters
        date_filter = {}
        if start_date:
            try:
                date_filter['$gte'] = datetime.fromisoformat(start_date)
            except Exception:
                try:
                    date_filter['$gte'] = datetime.fromtimestamp(float(start_date), tz=IST_TZ)
                except Exception:
                    pass
        if end_date:
            try:
                date_filter['$lte'] = datetime.fromisoformat(end_date)
            except Exception:
                try:
                    date_filter['$lte'] = datetime.fromtimestamp(float(end_date), tz=IST_TZ)
                except Exception:
                    pass
        if date_filter:
            query['created_at'] = date_filter

        # Include account scoping if present on records
        query['account_key'] = account_key

        # Perform query with limit/skip
        activities = list(repo.collection.find(query).sort('created_at', -1).skip(skip).limit(limit))
        # Convert ObjectIds/datetimes if needed in response (light normalization)
        for a in activities:
            if 'created_at' in a and hasattr(a['created_at'], 'isoformat'):
                a['created_at'] = a['created_at'].isoformat()
        return respond_success({'pondId': pond_id, 'activities': activities})
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception(f'Exception in pond_activity: {e}')
        return respond_error('Server error', status=500)


# GET /pond/<pond_id>/history - combine pond events, activity samples and analytics
@pond_bp.route('/<pond_id>/history', methods=['GET'])
def pond_history(pond_id):
    """Return combined history for a pond. Query params:
       - start_date (ISO)
       - end_date (ISO)
       - species_code (optional)
       - include_events (true/false)
       - include_activities (true/false)
       - include_analytics (true/false)
       - limit (int, default 100)
       - skip (int, default 0)
    """
    try:
        payload = get_auth_payload(request)
        account_key = payload.get('account_key')
        q = request.args
        start_date = q.get('start_date')
        end_date = q.get('end_date')
        species_code = q.get('species_code')
        include_events = str(q.get('include_events', 'true')).lower() != 'false'
        include_activities = str(q.get('include_activities', 'true')).lower() != 'false'
        include_analytics = str(q.get('include_analytics', 'true')).lower() != 'false'
        limit = int(q.get('limit', 100))
        skip = int(q.get('skip', 0))

        from fin_server.repository.pond_event_repository import PondEventRepository
        from fin_server.repository.fish_activity_repository import FishActivityRepository
        from fin_server.repository.fish_analytics_repository import FishAnalyticsRepository

        pond_event_repo = PondEventRepository()
        fish_activity_repo = FishActivityRepository()
        fish_analytics_repo = FishAnalyticsRepository()

        # helper to parse dates
        def _parse_dt(s):
            if not s:
                return None
            try:
                return datetime.fromisoformat(s)
            except Exception:
                try:
                    # fallback to timestamp
                    return datetime.fromtimestamp(float(s), tz=IST_TZ)
                except Exception:
                    return None

        sd = _parse_dt(start_date)
        ed = _parse_dt(end_date)

        result = {'pond_id': pond_id, 'account_key': account_key}

        # EVENTS
        events_out = []
        if include_events:
            events = pond_event_repo.get_events_by_pond(pond_id)
            # filter by date range
            filtered = []
            for e in events:
                dt = e.get('created_at')
                if isinstance(dt, str):
                    try:
                        dt = datetime.fromisoformat(dt)
                    except Exception:
                        dt = None
                if sd and dt and dt < sd:
                    continue
                if ed and dt and dt > ed:
                    continue
                if species_code and e.get('fish_id') != species_code:
                    continue
                filtered.append(e)
            events_out = filtered[skip:skip+limit]
        result['events'] = events_out

        # ACTIVITIES
        activities_out = []
        if include_activities:
            query = {'pond_id': pond_id}
            if species_code:
                query['fish_id'] = species_code
            activities = fish_activity_repo.find(query)
            filtered = []
            for a in activities:
                dt = a.get('created_at')
                if isinstance(dt, str):
                    try:
                        dt = datetime.fromisoformat(dt)
                    except Exception:
                        dt = None
                if sd and dt and dt < sd:
                    continue
                if ed and dt and dt > ed:
                    continue
                filtered.append(a)
            activities_out = filtered[skip:skip+limit]
        result['activities'] = activities_out

        # ANALYTICS (batches) - include batches for species seen on this pond or provided species_code
        analytics_out = []
        if include_analytics:
            species_to_check = set()
            if species_code:
                species_to_check.add(species_code)
            else:
                # gather species from events in the window
                for e in result.get('events', []):
                    fid = e.get('fish_id')
                    if fid:
                        species_to_check.add(fid)
            # fetch batches for each species and filter by date_added
            for sid in species_to_check:
                batches = fish_analytics_repo.get_batches(sid, account_key=account_key)
                filtered = []
                for b in batches:
                    dt = b.get('date_added')
                    if isinstance(dt, str):
                        try:
                            dt = datetime.fromisoformat(dt)
                        except Exception:
                            dt = None
                    if sd and dt and dt < sd:
                        continue
                    if ed and dt and dt > ed:
                        continue
                    filtered.append(b)
                analytics_out.extend(filtered)
            # dedupe/sort by date_added desc
            analytics_out = sorted(analytics_out, key=lambda x: x.get('date_added') or datetime.min, reverse=True)
            analytics_out = analytics_out[skip:skip+limit]
        result['analytics'] = analytics_out

        # Normalize nested BSON types (ObjectId) and datetimes
        result_normalized = normalize_doc(result)
        return respond_success({'history': result_normalized})
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception(f'Exception in pond_history: {e}')
        return respond_error('Server error', status=500)


# New: API helpers (canonical pond API functions used by /api/compat shim)
def api_list_ponds():
    """Return Flask response listing ponds for authenticated account (used by compat layer)."""
    try:
        payload = get_request_payload()
        account_key = payload.get('account_key')
        args = request.args
        limit, skip, perr = parse_pagination(args, default_limit=100, max_limit=1000)
        if perr:
            return respond_error(perr, status=400)
        other_filters = {}
        reserved = {'limit', 'skip', 'page', 'from_date', 'to_date', 'sort', 'order', 'account_key'}
        for k, v in args.items():
            if k in reserved:
                continue
            if v is not None and v != '':
                other_filters[k] = v
        date_filter = {}
        from_date = args.get('from_date')
        to_date = args.get('to_date')
        if from_date:
            try:
                date_filter['$gte'] = datetime.fromisoformat(from_date)
            except Exception:
                try:
                    date_filter['$gte'] = datetime.fromtimestamp(float(from_date), tz=IST_TZ)
                except Exception:
                    pass
        if to_date:
            try:
                date_filter['$lte'] = datetime.fromisoformat(to_date)
            except Exception:
                try:
                    date_filter['$lte'] = datetime.fromtimestamp(float(to_date), tz=IST_TZ)
                except Exception:
                    pass
        if date_filter:
            other_filters['created_at'] = date_filter
        or_clause = [ {'account_key': account_key}, {'account_key': {'$exists': False}, 'pond_id': {'$regex': f'^{account_key}-'}} ]
        final_query = {'$and': [ {'$or': or_clause}, other_filters ]} if other_filters else {'$or': or_clause}
        cursor = pond_repository.collection.find(final_query).sort('created_at', -1).skip(skip).limit(limit)
        pond_list = list(cursor)
        out_list = []
        for p in pond_list:
            try:
                pd = PondDTO.from_doc(p)
                out_list.append(pd.to_dict())
            except Exception:
                out_list.append(pond_to_dict(p))
        return respond_success({'data': out_list, 'meta': {'limit': limit, 'skip': skip}})
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception('Error in api_list_ponds')
        return respond_error('Server error', status=500)


def api_create_pond():
    """Create pond (used by compat shim)."""
    try:
        payload = get_request_payload()
        data = request.get_json(force=True)
        account_key = payload.get('account_key')
        data.pop('account_key', None)
        data['created_at'] = get_time_date_dt(include_time=True)
        pond_id = data.get('pond_id')
        if not pond_id:
            next_num = get_next_pond_number(account_key)
            pond_id = f"{account_key}-{next_num:03d}"
            data['pond_id'] = pond_id
        existing = pond_repository.find_one({'pond_id': pond_id})
        if existing:
            return respond_error('Pond with this pond_id already exists.', status=409)
        pond_entity = data.copy()
        pond_entity['_id'] = pond_id
        pond_entity['account_key'] = account_key
        try:
            pdto = PondDTO.from_request(pond_entity)
            pdto.save(repo=pond_repository, collection_name='ponds', upsert=True)
            return respond_success({'pond_id': pond_id}, status=201)
        except Exception:
            res = pond_repository.create(pond_entity)
            return respond_success({'pond_id': pond_id}, status=201)
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception('Error in api_create_pond')
        return respond_error('Server error', status=500)


def api_get_pond(pond_id):
    try:
        payload = get_request_payload()
        account_key = payload.get('account_key')
        pond = pond_repository.find_one({'pond_id': pond_id, 'account_key': account_key})
        if not pond:
            return respond_error('Pond not found', status=404)
        try:
            pd = PondDTO.from_doc(pond)
            return respond_success({'pond': pd.to_dict()})
        except Exception:
            return respond_success({'pond': pond_to_dict(pond)})
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception('Error in api_get_pond')
        return respond_error('Server error', status=500)


def api_patch_pond(pond_id):
    try:
        payload = get_request_payload()
        data = request.get_json(force=True)
        data.pop('_id', None)
        data.pop('account_key', None)
        result = pond_repository.update({'pond_id': pond_id, 'account_key': payload.get('account_key')}, data)
        if not result or not result.modified_count:
            return respond_error('Pond not found or nothing updated.', status=404)
        updated = pond_repository.find_one({'pond_id': pond_id})
        try:
            pd = PondDTO.from_doc(updated)
            return respond_success({'pond': pd.to_dict()})
        except Exception:
            return respond_success({'pond': pond_to_dict(updated)})
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception('Error in api_patch_pond')
        return respond_error('Server error', status=500)


def api_delete_pond(pond_id):
    try:
        payload = get_request_payload()
        result = pond_repository.delete({'pond_id': pond_id, 'account_key': payload.get('account_key')})
        if not result or not result.deleted_count:
            return respond_error('Pond not found', status=404)
        return respond_success({'deleted': True})
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception('Error in api_delete_pond')
        return respond_error('Server error', status=500)


from flask import Blueprint as _Blueprint

pond_api_bp = _Blueprint('pond_api', __name__, url_prefix='/api')

@pond_api_bp.route('/ponds', methods=['GET'])
def api_list_ponds_route():
    return api_list_ponds()

@pond_api_bp.route('/ponds', methods=['POST'])
def api_create_pond_route():
    return api_create_pond()

@pond_api_bp.route('/ponds/<pond_id>', methods=['GET'])
def api_get_pond_route(pond_id):
    return api_get_pond(pond_id)

@pond_api_bp.route('/ponds/<pond_id>', methods=['PATCH'])
def api_patch_pond_route(pond_id):
    return api_patch_pond(pond_id)

@pond_api_bp.route('/ponds/<pond_id>', methods=['DELETE'])
def api_delete_pond_route(pond_id):
    return api_delete_pond(pond_id)
