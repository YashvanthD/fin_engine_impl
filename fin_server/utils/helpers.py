from flask import jsonify, current_app, request
from fin_server.security.authentication import get_auth_payload
from fin_server.exception.UnauthorizedError import UnauthorizedError
from datetime import datetime, timezone
import zoneinfo
from werkzeug.exceptions import Forbidden


def respond_error(message_or_dict, status=400):
    """Return a standardized error response compatible with frontend expectations.

    - If a string is passed, returns { success: False, 'message': str, 'error': str }.
    - If a dict is passed, returns { success: False, 'errors': dict, 'message': first message }.
    """
    body = {'success': False}
    if isinstance(message_or_dict, dict):
        body['errors'] = message_or_dict
        # try to build a short message from first error
        try:
            first = next(iter(message_or_dict.values()))
            if isinstance(first, list) and first:
                body['message'] = str(first[0])
            else:
                body['message'] = str(first)
        except Exception:
            body['message'] = 'Validation error'
    else:
        body['message'] = str(message_or_dict)
        body['error'] = str(message_or_dict)
    # always include a timestamp for debugging by frontend (IST)
    ist = zoneinfo.ZoneInfo('Asia/Kolkata')
    body['timestamp'] = datetime.now(ist).isoformat()
    # prune None values before returning
    try:
        body = _prune_none(body)
    except Exception:
        current_app.logger.exception('Failed to prune None in respond_error')
    return jsonify(body), status


def _snake_to_camel(s: str) -> str:
    """Convert snake_case or kebab-case to camelCase for frontend compatibility."""
    if not s:
        return s
    s = str(s)
    # handle leading underscores (private fields) - keep them
    if s.startswith('_'):
        # convert the rest
        return '_' + _snake_to_camel(s.lstrip('_'))
    parts = s.replace('-', '_').split('_')
    if len(parts) == 1:
        return parts[0]
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])


def normalize_doc(obj):
    """Recursively convert BSON types (ObjectId) and datetimes to JSON-serializable values.

    - ObjectId -> str(ObjectId)
    - datetime -> ISO string
    - recursively handles dicts and lists
    Returns a new object (does not mutate input) for safety.
    """
    try:
        from bson import ObjectId
    except Exception:
        ObjectId = None

    if obj is None:
        return None
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            out[k] = normalize_doc(v)
        return out
    if isinstance(obj, list):
        return [normalize_doc(v) for v in obj]
    if ObjectId is not None and isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    # default: return as-is
    return obj


def _ensure_id_aliases(d: dict):
    """Given a dict with possible keys like userKey/user_key, pondId/pond_id, taskId/task_id,
    ensure there's an `id` field with the preferred frontend id.
    This mutates the dict in-place.
    """
    # If id already present and non-empty, keep it
    if 'id' in d and d.get('id'):
        return
    # possible primary id keys in order of preference
    for key in ('userKey', 'user_key', 'userId', 'user_id', 'pondId', 'pond_id', 'pondId', 'pond_id', 'taskId', 'task_id', 'id', '_id'):
        if key in d and d.get(key) not in (None, ''):
            d['id'] = d.get(key)
            return


def _transform_keys_and_types(obj):
    """Recursively convert a normalized doc (with primitive values) into frontend-friendly shape:
    - convert keys to camelCase
    - ensure `id` aliases are present (from user_key/pond_id/task_id/_id)
    - convert boolean-like strings to booleans? (not by default)
    Returns a new object.
    """
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_transform_keys_and_types(v) for v in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            newk = _snake_to_camel(k)
            out[newk] = _transform_keys_and_types(v)
        # after building, ensure common id aliases
        _ensure_id_aliases(out)
        return out
    # primitives: str, int, float, bool - return as-is
    return obj


def _to_iso_if_epoch(val):
    """If val is an int/float epoch or numeric string, convert to ISO string; if already ISO string, keep as-is."""
    if val is None:
        return None
    try:
        if isinstance(val, (int, float)):
            return datetime.fromtimestamp(float(val), tz=timezone.utc).isoformat()
        s = str(val)
        # if numeric string
        if s.isdigit():
            return datetime.fromtimestamp(float(s), tz=timezone.utc).isoformat()
        # try parse as ISO
        try:
            dt = datetime.fromisoformat(s)
            return dt.isoformat()
        except Exception:
            return s
    except Exception:
        return str(val)


def _post_normalize(obj):
    """Apply specific field-name and type mappings expected by the frontend.
    Mutates the object in-place and returns it. Designed to run after camelCase conversion.
    Rules implemented:
      - joinedDate -> createdAt (convert epoch -> ISO)
      - date (for feeding) -> feedingTime (ISO)
      - feedQuantity -> quantity (float)
      - taskDate -> scheduledDate
      - startTime/endTime ensure ISO strings
      - avgWeight ensure numeric
    """
    if obj is None:
        return obj
    if isinstance(obj, list):
        for item in obj:
            _post_normalize(item)
        return obj
    if not isinstance(obj, dict):
        return obj

    # Users: joinedDate -> createdAt
    if 'joinedDate' in obj and 'createdAt' not in obj:
        obj['createdAt'] = _to_iso_if_epoch(obj.pop('joinedDate'))

    # Combine firstName/lastName into name for frontend if present
    if 'name' not in obj:
        fn = obj.get('firstName') or obj.get('first_name')
        ln = obj.get('lastName') or obj.get('last_name')
        if fn or ln:
            full = ((fn or '') + ' ' + (ln or '')).strip()
            if full:
                obj['name'] = full

    # Pond: pondName -> name (frontend expects 'name')
    if 'pondName' in obj and 'name' not in obj:
        obj['name'] = obj.pop('pondName')
    if 'pond_name' in obj and 'name' not in obj:
        obj['name'] = obj.pop('pond_name')

    # Pond: map waterType -> type, pond may use 'waterType' or 'water_type'
    if 'type' not in obj:
        if 'waterType' in obj:
            obj['type'] = obj.pop('waterType')
        elif 'water_type' in obj:
            obj['type'] = obj.pop('water_type')

    # Ensure dimensions is an object with numeric fields
    if 'dimensions' in obj and isinstance(obj.get('dimensions'), dict):
        dims = obj['dimensions']
        for k in ('length', 'width', 'depth'):
            if k in dims:
                try:
                    dims[k] = float(dims[k]) if dims[k] is not None and dims[k] != '' else None
                except Exception:
                    dims[k] = None

    # Location: if location is string but latitude/longitude present, prefer structured object
    if 'location' in obj:
        loc = obj['location']
        if isinstance(loc, str):
            # try to keep string if no coordinates available
            lat = obj.pop('latitude', None) or obj.pop('lat', None)
            lon = obj.pop('longitude', None) or obj.pop('lon', None)
            if lat is not None or lon is not None:
                try:
                    obj['location'] = {'latitude': float(lat) if lat is not None else None, 'longitude': float(lon) if lon is not None else None}
                except Exception:
                    obj['location'] = {'latitude': lat, 'longitude': lon}
        elif isinstance(loc, dict):
            # Normalize nested keys to latitude/longitude
            if 'lat' in loc and 'latitude' not in loc:
                loc['latitude'] = loc.pop('lat')
            if 'lon' in loc and 'longitude' not in loc:
                loc['longitude'] = loc.pop('lon')
            # coerce to numbers
            try:
                if 'latitude' in loc and loc['latitude'] is not None:
                    loc['latitude'] = float(loc['latitude'])
                if 'longitude' in loc and loc['longitude'] is not None:
                    loc['longitude'] = float(loc['longitude'])
            except Exception:
                pass

    # StockRecord: ensure numeric fields and expected naming
    if 'currentStock' in obj and isinstance(obj['currentStock'], list):
        for s in obj['currentStock']:
            # camelCase already applied; ensure numeric conversions
            for numk in ('quantity', 'averageWeight', 'sampleSize'):
                if numk in s:
                    try:
                        s[numk] = float(s[numk]) if s[numk] is not None and s[numk] != '' else None
                    except Exception:
                        s[numk] = None
            # date fields -> ISO if epoch
            for dk in ('stockingDate', 'expectedHarvestDate', 'samplingDate'):
                if dk in s and s[dk] is not None and not isinstance(s[dk], str):
                    try:
                        s[dk] = _to_iso_if_epoch(s[dk])
                    except Exception:
                        s[dk] = str(s[dk])

    # WaterQualityRecord: ensure parameters keys are numeric
    if 'parameters' in obj and isinstance(obj['parameters'], dict):
        for pk, pv in list(obj['parameters'].items()):
            try:
                obj['parameters'][pk] = float(pv) if pv is not None and pv != '' else None
            except Exception:
                obj['parameters'][pk] = None

    # Feeding record: normalize naming and numeric quantity
    if 'feedQuantity' in obj and 'quantity' not in obj:
        try:
            obj['quantity'] = float(obj.pop('feedQuantity')) if obj.get('feedQuantity') is not None else None
        except Exception:
            obj['quantity'] = None
    if 'feedingTime' in obj and obj.get('feedingTime') is not None:
        obj['feedingTime'] = _to_iso_if_epoch(obj['feedingTime'])

    # Sampling/Growth: ensure numeric averages
    if 'averageWeight' in obj:
        try:
            obj['averageWeight'] = float(obj['averageWeight']) if obj.get('averageWeight') is not None else None
        except Exception:
            obj['averageWeight'] = None
    if 'averageLength' in obj:
        try:
            obj['averageLength'] = float(obj['averageLength']) if obj.get('averageLength') is not None else None
        except Exception:
            obj['averageLength'] = None

    # Alerts: ensure boolean acknowledged
    if 'acknowledged' in obj:
        if isinstance(obj['acknowledged'], str):
            obj['acknowledged'] = obj['acknowledged'].lower() in ('true', '1', 'yes')

    # Tasks: normalize scheduledDate/startTime/endTime/completedDate
    if 'scheduledDate' in obj:
        obj['scheduledDate'] = _to_iso_if_epoch(obj['scheduledDate'])
    if 'startTime' in obj:
        obj['startTime'] = _to_iso_if_epoch(obj['startTime'])
    if 'endTime' in obj:
        obj['endTime'] = _to_iso_if_epoch(obj['endTime'])
    if 'completedDate' in obj:
        obj['completedDate'] = _to_iso_if_epoch(obj['completedDate'])

    # Task field name compatibility: task_date -> scheduledDate, end_date -> endTime, assigned_to/assignee -> assignedTo, reporter -> reporter/user
    if 'task_date' in obj and 'scheduledDate' not in obj:
        obj['scheduledDate'] = _to_iso_if_epoch(obj.pop('task_date'))
    if 'taskDate' in obj and 'scheduledDate' not in obj:
        obj['scheduledDate'] = _to_iso_if_epoch(obj.pop('taskDate'))
    if 'end_date' in obj and 'endTime' not in obj:
        obj['endTime'] = _to_iso_if_epoch(obj.pop('end_date'))
    if 'endDate' in obj and 'endTime' not in obj:
        obj['endTime'] = _to_iso_if_epoch(obj.pop('endDate'))
    # start_time / startTime
    if 'start_time' in obj and 'startTime' not in obj:
        obj['startTime'] = _to_iso_if_epoch(obj.pop('start_time'))
    if 'startTime' in obj:
        obj['startTime'] = _to_iso_if_epoch(obj['startTime'])
    # assignedTo mapping
    if 'assigned_to' in obj and 'assignedTo' not in obj:
        obj['assignedTo'] = obj.pop('assigned_to')
    if 'assignee' in obj and 'assignedTo' not in obj:
        obj['assignedTo'] = obj.pop('assignee')
    # Map task type names
    if 'taskType' in obj and isinstance(obj['taskType'], str):
        # keep as-is; frontend accepts 'Feeding'|'Sampling' etc.
        pass

    # StockRecord field mappings inside currentStock array items
    if 'currentStock' in obj and isinstance(obj['currentStock'], list):
        for s in obj['currentStock']:
            if 'batch_id' in s and 'batchId' not in s:
                s['batchId'] = s.pop('batch_id')
            if 'stocking_date' in s and 'stockingDate' not in s:
                s['stockingDate'] = _to_iso_if_epoch(s.pop('stocking_date'))
            if 'expected_harvest_date' in s and 'expectedHarvestDate' not in s:
                s['expectedHarvestDate'] = _to_iso_if_epoch(s.pop('expected_harvest_date'))
            if 'average_weight' in s and 'averageWeight' not in s:
                try:
                    s['averageWeight'] = float(s.pop('average_weight')) if s.get('average_weight') not in (None, '') else None
                except Exception:
                    s['averageWeight'] = None
            if 'species' not in s and 'species_code' in s:
                s['species'] = s.get('species_code')
            # Ensure id alias for stock record
            if 'id' not in s:
                if 'stock_id' in s:
                    s['id'] = s.get('stock_id')
                elif '_id' in s:
                    s['id'] = str(s.get('_id'))

    # WaterQuality records: timestamp normalization and recordedBy
    if 'timestamp' in obj and isinstance(obj.get('timestamp'), (int, float, str)):
        obj['timestamp'] = _to_iso_if_epoch(obj['timestamp'])
    if 'recorded_by' in obj and 'recordedBy' not in obj:
        obj['recordedBy'] = obj.pop('recorded_by')

    # Alerts mapping
    if 'acknowledged_by' in obj and 'acknowledgedBy' not in obj:
        obj['acknowledgedBy'] = obj.pop('acknowledged_by')
    if 'acknowledged_at' in obj and 'acknowledgedAt' not in obj:
        obj['acknowledgedAt'] = _to_iso_if_epoch(obj.pop('acknowledged_at'))

    # GrowthRecord naming compatibility
    if 'sampling_date' in obj and 'samplingDate' not in obj:
        obj['samplingDate'] = _to_iso_if_epoch(obj.pop('sampling_date'))
    if 'sample_size' in obj and 'sampleSize' not in obj:
        try:
            obj['sampleSize'] = int(obj.pop('sample_size'))
        except Exception:
            obj['sampleSize'] = None
    if 'survival_rate' in obj and 'survivalRate' not in obj:
        try:
            obj['survivalRate'] = float(obj.pop('survival_rate'))
        except Exception:
            obj['survivalRate'] = None
    if 'feed_conversion_ratio' in obj and 'feedConversionRatio' not in obj:
        try:
            obj['feedConversionRatio'] = float(obj.pop('feed_conversion_ratio'))
        except Exception:
            obj['feedConversionRatio'] = None

    # Recurring normalization: allow frequency names and end_date mapping
    if 'recurring' in obj and isinstance(obj['recurring'], dict):
        if 'end_date' in obj['recurring'] and 'endDate' not in obj['recurring']:
            obj['recurring']['endDate'] = _to_iso_if_epoch(obj['recurring'].pop('end_date'))
        if 'frequency' in obj['recurring']:
            obj['recurring']['frequency'] = obj['recurring']['frequency']

    # Recurse into nested dicts
    for k, v in list(obj.items()):
        if isinstance(v, dict) or isinstance(v, list):
            _post_normalize(v)
    return obj


def normalize_for_ui(obj):
    """Full normalization pipeline for outgoing responses to UI:
    1) normalize datetimes/ObjectId -> strings using normalize_doc
    2) transform keys to camelCase and add `id` where applicable
    3) apply post-normalization mappings for frontend expectations
    Returns a new object safe for JSON serialization.
    """
    normalized = normalize_doc(obj)
    transformed = _transform_keys_and_types(normalized)
    try:
        _post_normalize(transformed)
    except Exception:
        current_app.logger.exception('Post-normalization failed')
    return transformed


def respond_success(payload=None, status=200):
    """Return a standardized success response compatible with frontend's ApiResponse.

    - If payload is None -> { success: True, data: {} }
    - If payload is a dict and already contains 'data' key, return as-is (with timestamp)
    - Otherwise wrap payload into 'data' key: { success: True, data: payload }
    Also attach a timestamp. Before returning, normalize the `data` to UI shape.
    """
    if payload is None:
        data = {}
    else:
        data = payload

    body = {'success': True}
    if isinstance(data, dict) and 'data' in data:
        # caller already provided envelope-like object
        body.update(data)
    else:
        body['data'] = data

    # Normalize the data payload for UI (convert keys/types) and remove None values
    try:
        # normalize_for_ui may throw; wrap
        body['data'] = normalize_for_ui(body['data'])
    except Exception:
        current_app.logger.exception('Failed to normalize response payload for UI')
    try:
        body['data'] = _prune_none(body['data'])
    except Exception:
        current_app.logger.exception('Failed to prune None in respond_success')
    # IST timestamp for success responses
    body['timestamp'] = datetime.now(IST_TZ).isoformat()
    return jsonify(body), status


def get_request_payload(req=None, required_role: str = None, account_key: str = None):
    """Decode auth token from request and optionally enforce authorization.

    Parameters:
    - req: Flask request object (defaults to flask.request)
    - required_role: if provided, the decoded payload must include this role (raises 403 otherwise)
    - account_key: if provided, the decoded payload must have matching account_key (raises 403 otherwise)

    Raises:
    - UnauthorizedError: when authentication fails (401)
    - Forbidden: when token is valid but user is not authorized (403)
    """
    if req is None:
        req = request
    try:
        payload = get_auth_payload(req)
    except UnauthorizedError as e:
        current_app.logger.warning(f'Auth failure: {e}')
        # Preserve project-specific UnauthorizedError so existing code paths catch it
        raise UnauthorizedError(str(e))

    # Authorization checks (optional)
    try:
        if required_role:
            roles = []
            if isinstance(payload.get('roles'), list):
                roles = payload.get('roles', [])
            elif payload.get('role'):
                roles = [payload.get('role')]
            if required_role not in roles:
                current_app.logger.warning(f'Authorization failure: missing role {required_role} in token')
                raise Forbidden(f'Missing required role: {required_role}')

        if account_key:
            tok_acct = payload.get('account_key')
            if tok_acct != account_key:
                current_app.logger.warning(f'Authorization failure: token account_key {tok_acct} does not match required {account_key}')
                raise Forbidden('Account mismatch or not authorized for this account')
    except Forbidden:
        # Re-raise Forbidden to be handled by Flask as 403
        raise

    return payload


IST_TZ = zoneinfo.ZoneInfo('Asia/Kolkata')


def parse_iso_or_epoch(s):
    """Parse ISO datetime or epoch string/number into aware IST datetime or return None."""
    if not s:
        return None
    try:
        if isinstance(s, (int, float)):
            return datetime.fromtimestamp(float(s), tz=IST_TZ)
        s = str(s)
        # try ISO first
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=IST_TZ)
            else:
                dt = dt.astimezone(IST_TZ)
            return dt
        except Exception:
            pass
        try:
            return datetime.fromtimestamp(float(s), tz=IST_TZ)
        except Exception:
            return None
    except Exception:
        return None


def normalize_datetime_fields(doc):
    """Recursively convert datetime objects in a dict/list to isoformat strings (in-place)"""
    if isinstance(doc, dict):
        for k, v in doc.items():
            if isinstance(v, datetime):
                try:
                    doc[k] = v.isoformat()
                except Exception:
                    doc[k] = str(v)
            elif isinstance(v, (dict, list)):
                normalize_datetime_fields(v)
    elif isinstance(doc, list):
        for i in range(len(doc)):
            v = doc[i]
            if isinstance(v, datetime):
                try:
                    doc[i] = v.isoformat()
                except Exception:
                    doc[i] = str(v)
            elif isinstance(v, (dict, list)):
                normalize_datetime_fields(v)
    return doc


def parse_pagination(args, default_limit=100, max_limit=1000):
    errors = {}
    # Initialize with defaults to ensure variables exist
    limit = default_limit
    skip = 0
    try:
        limit = int(args.get('limit', default_limit))
        if limit < 1 or limit > max_limit:
            errors['limit'] = f'limit must be between 1 and {max_limit}'
    except Exception:
        errors['limit'] = 'limit must be an integer'
    try:
        skip = int(args.get('skip', 0))
        if skip < 0:
            errors['skip'] = 'skip must be >= 0'
    except Exception:
        errors['skip'] = 'skip must be an integer'
    if errors:
        return None, None, errors
    return limit, skip, None


def _prune_none(obj):
    """Recursively remove keys with None values and None items in lists.

    Keeps empty strings and falsy but non-None values (0, False, []).
    Returns a new object (does not mutate input) to be safe.
    """
    if obj is None:
        return None
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            pv = _prune_none(v)
            if pv is None:
                continue
            out[k] = pv
        return out
    if isinstance(obj, list):
        out = []
        for v in obj:
            pv = _prune_none(v)
            if pv is None:
                continue
            out.append(pv)
        return out
    return obj


def clean_for_ui(obj):
    """Normalize an object for UI and remove None values.

    This composes the existing normalize_for_ui pipeline, then prunes None
    entries so responses won't include nulls. Use this from global middleware
    before sending JSON responses.
    """
    try:
        transformed = normalize_for_ui(obj)
    except Exception:
        current_app.logger.exception('normalize_for_ui failed in clean_for_ui')
        # fallback: try to at least prune the original
        return _prune_none(obj)
    try:
        return _prune_none(transformed)
    except Exception:
        current_app.logger.exception('Prune None failed in clean_for_ui')
        return transformed
