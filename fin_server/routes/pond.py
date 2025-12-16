from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone
from fin_server.repository.pond_repository import PondRepository
from fin_server.security.authentication import get_auth_payload
from fin_server.utils.helpers import get_request_payload, parse_pagination
from fin_server.utils.helpers import normalize_doc
from fin_server.exception.UnauthorizedError import UnauthorizedError

pond_bp = Blueprint('pond', __name__, url_prefix='/pond')
pond_repository = PondRepository()

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
        data['created_at'] = datetime.now(timezone.utc)
        # Generate pond_id if not provided, using auto-increment
        pond_id = data.get('pond_id')
        if not pond_id:
            next_num = get_next_pond_number(account_key)
            pond_id = f"{account_key}-{next_num:03d}"
            data['pond_id'] = pond_id
        # Check for duplicate pond_id
        existing = pond_repository.find_one({'pond_id': pond_id})
        if existing:
            return jsonify({'success': False, 'error': 'Pond with this pond_id already exists.'}), 409
        # Insert pond entity (ensure account_key is saved)
        pond_entity = data.copy()
        pond_entity['_id'] = pond_id
        pond_entity['account_key'] = account_key
        pond_repository.create(pond_entity)
        return jsonify({'success': True, 'pond_id': pond_id}), 201
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        current_app.logger.exception(f'Exception in create_pond_entity: {e}')
        return jsonify({'success': False, 'error': 'Server error'}), 500

@pond_bp.route('/update/<pond_id>', methods=['PUT'])
def update_pond_entity(pond_id):
    current_app.logger.info(f'PUT /pond/update/{pond_id} called')
    try:
        payload = get_auth_payload(request)
        data = request.get_json(force=True)
        # Only allow updating certain fields (not _id/account_key)
        update_fields = {k: v for k, v in data.items() if k not in ['_id', 'account_key', 'pond_id']}
        if not update_fields:
            return jsonify({'success': False, 'error': 'No updatable fields provided.'}), 400
        account_key = payload.get('account_key')
        result = pond_repository.update({'pond_id': pond_id, 'account_key': account_key}, update_fields)
        if not result or not result.modified_count:
            return jsonify({'success': False, 'error': 'Pond not found or nothing updated.'}), 404
        return jsonify({'success': True, 'pond_id': pond_id}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        current_app.logger.exception(f'Exception in update_pond_entity: {e}')
        return jsonify({'success': False, 'error': 'Server error'}), 500

@pond_bp.route('/<pond_id>', methods=['GET'])
def get_pond(pond_id):
    current_app.logger.debug('GET pond/%s called', pond_id)
    try:
        payload = get_auth_payload(request)

        # enforce account scoping
        account_key = payload.get('account_key')
        pond = pond_repository.find_one({'pond_id': pond_id, 'account_key': account_key})
        if not pond:
            return jsonify({'success': False, 'error': 'Pond not found'}), 404
        return jsonify({'success': True, 'pond': pond_to_dict(pond)}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500

@pond_bp.route('/<pond_id>', methods=['PUT'])
def update_pond(pond_id):
    current_app.logger.debug('PUT /pond/%s called with data: %s', pond_id, request.json)
    try:
        payload = get_auth_payload(request)
        data = request.get_json(force=True)
        account_key = payload.get('account_key')
        result = pond_repository.update({'pond_id': pond_id, 'account_key': account_key}, data)
        if not result or not result.modified_count:
            return jsonify({'success': False, 'error': 'Pond not found or nothing updated.'}), 404
        return jsonify({'success': True, 'updated': True}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500

@pond_bp.route('/<pond_id>', methods=['DELETE'])
def delete_pond(pond_id):
    current_app.logger.debug('DELETE /pond/%s called', pond_id)
    try:
        payload = get_auth_payload(request)
        account_key = payload.get('account_key')
        result = pond_repository.delete({'pond_id': pond_id, 'account_key': account_key})
        if not result or not result.deleted_count:
            return jsonify({'success': False, 'error': 'Pond not found'}), 404
        return jsonify({'success': True, 'deleted': True}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500

@pond_bp.route('/', methods=['GET'])
def list_ponds():
    current_app.logger.debug('GET /pond/ called with query: %s', request.args)
    try:
        payload = get_request_payload(request)
        account_key = payload.get('account_key')
        args = request.args

        # Parse pagination params first (validate)
        limit, skip, perr = parse_pagination(args, default_limit=100, max_limit=1000)
        if perr:
            return jsonify({'success': False, 'errors': perr}), 400

        # Build other_filters from query params (exclude reserved params)
        other_filters = {}
        reserved = {'limit', 'skip', 'page', 'from_date', 'to_date', 'sort', 'order', 'account_key'}
        for k, v in args.items():
            if k in reserved:
                continue
            if v is not None and v != '':
                other_filters[k] = v

        # Date range filter support for created_at
        date_filter = {}
        from_date = args.get('from_date')
        to_date = args.get('to_date')
        if from_date:
            try:
                date_filter['$gte'] = datetime.fromisoformat(from_date)
            except Exception:
                try:
                    date_filter['$gte'] = datetime.fromtimestamp(float(from_date), tz=timezone.utc)
                except Exception:
                    pass
        if to_date:
            try:
                date_filter['$lte'] = datetime.fromisoformat(to_date)
            except Exception:
                try:
                    date_filter['$lte'] = datetime.fromtimestamp(float(to_date), tz=timezone.utc)
                except Exception:
                    pass
        if date_filter:
            other_filters['created_at'] = date_filter

        # Build final query: include docs with matching account_key OR legacy docs with missing account_key but pond_id starting with account_key
        or_clause = [ {'account_key': account_key}, {'account_key': {'$exists': False}, 'pond_id': {'$regex': f'^{account_key}-'}} ]
        if other_filters:
            final_query = {'$and': [ {'$or': or_clause}, other_filters ]}
        else:
            final_query = {'$or': or_clause}

        # Execute query with pagination
        cursor = pond_repository.collection.find(final_query).sort('created_at', -1).skip(skip).limit(limit)
        pond_list = list(cursor)
        return jsonify({'success': True, 'ponds': [pond_to_dict(p) for p in pond_list], 'meta': {'limit': limit, 'skip': skip}}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500


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
        return jsonify({'success': True, 'pond_id': pond_id, 'options': options}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        current_app.logger.exception(f'Exception in pond_fish_options: {e}')
        return jsonify({'success': False, 'error': 'Server error'}), 500


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
                    date_filter['$gte'] = datetime.fromtimestamp(float(start_date), tz=timezone.utc)
                except Exception:
                    pass
        if end_date:
            try:
                date_filter['$lte'] = datetime.fromisoformat(end_date)
            except Exception:
                try:
                    date_filter['$lte'] = datetime.fromtimestamp(float(end_date), tz=timezone.utc)
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
        return jsonify({'success': True, 'pond_id': pond_id, 'activities': activities}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        current_app.logger.exception(f'Exception in pond_activity: {e}')
        return jsonify({'success': False, 'error': 'Server error'}), 500


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
                    return datetime.fromtimestamp(float(s), tz=timezone.utc)
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
        return jsonify({'success': True, 'history': result_normalized}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        current_app.logger.exception(f'Exception in pond_history: {e}')
        return jsonify({'success': False, 'error': 'Server error'}), 500

