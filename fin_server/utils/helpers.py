from flask import jsonify, current_app, request
from fin_server.security.authentication import get_auth_payload
from fin_server.exception.UnauthorizedError import UnauthorizedError
from datetime import datetime, timezone


def respond_error(message_or_dict, status=400):
    """Return a standardized error response."""
    if isinstance(message_or_dict, dict):
        body = {'success': False, 'errors': message_or_dict}
    else:
        body = {'success': False, 'error': message_or_dict}
    return jsonify(body), status


def respond_success(payload=None, status=200):
    if payload is None:
        payload = {}
    body = {'success': True}
    if isinstance(payload, dict):
        body.update(payload)
    else:
        body['data'] = payload
    return jsonify(body), status


def get_request_payload(req=None):
    """Decode auth token from request or raise UnauthorizedError with clear message."""
    if req is None:
        req = request
    try:
        return get_auth_payload(req)
    except UnauthorizedError as e:
        current_app.logger.warning(f'Auth failure: {e}')
        raise


def parse_iso_or_epoch(s):
    """Parse ISO datetime or epoch string/number into aware UTC datetime or return None."""
    if not s:
        return None
    try:
        if isinstance(s, (int, float)):
            return datetime.fromtimestamp(float(s), tz=timezone.utc)
        s = str(s)
        # try ISO first
        try:
            return datetime.fromisoformat(s)
        except Exception:
            pass
        try:
            return datetime.fromtimestamp(float(s), tz=timezone.utc)
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
