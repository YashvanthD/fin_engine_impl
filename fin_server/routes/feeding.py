"""Feeding routes for fish feeding records.

This module provides endpoints for:
- Feeding record creation
- Feeding record listing
- Feeding records by pond
"""
import logging

from flask import Blueprint, request

from fin_server.dto.feeding_dto import FeedingRecordDTO
from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.decorators import handle_errors, require_auth
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc

logger = logging.getLogger(__name__)

# Blueprint
feeding_bp = Blueprint('feeding', __name__, url_prefix='/feeding')

# Repository
feeding_repo = get_collection('feeding')


# =============================================================================
# Helper Functions
# =============================================================================

def _normalize_feeding_doc(doc):
    """Normalize feeding document to DTO format."""
    normalized = normalize_doc(doc)
    try:
        dto = FeedingRecordDTO.from_doc(normalized)
        return dto.to_dict()
    except Exception:
        normalized['_id'] = str(normalized.get('_id'))
        normalized['id'] = normalized.get('_id')
        return normalized


def _get_feeding_list(query):
    """Get list of feeding records matching query."""
    try:
        feeds = feeding_repo.find(query)
    except Exception:
        feeds = list(feeding_repo.find(query).sort('created_at', -1))

    return [_normalize_feeding_doc(f) for f in feeds]


# =============================================================================
# Feeding Endpoints
# =============================================================================

@feeding_bp.route('/', methods=['POST'])
@handle_errors
@require_auth
def create_feeding_route(auth_payload):
    """Create a new feeding record."""
    data = request.get_json(force=True)

    # Build DTO
    dto = FeedingRecordDTO.from_request(data)
    dto.recordedBy = auth_payload.get('user_key')

    # Persist
    try:
        res = dto.save(repo=feeding_repo)
        inserted_id = getattr(res, 'inserted_id', res)
        inserted_id = str(inserted_id) if inserted_id is not None else None
    except Exception:
        r = feeding_repo.insert_one(dto.to_db_doc())
        inserted_id = str(r.inserted_id)

    dto.id = inserted_id
    return respond_success(dto.to_dict(), status=201)


@feeding_bp.route('/', methods=['GET'])
@handle_errors
@require_auth
def list_feeding_route(auth_payload):
    """List all feeding records."""
    q = {}

    pond_id = request.args.get('pondId') or request.args.get('pond_id')
    if pond_id:
        q['pondId'] = pond_id

    feeds = _get_feeding_list(q)
    return respond_success(feeds)


@feeding_bp.route('/pond/<pond_id>', methods=['GET'])
@handle_errors
def feeding_by_pond_route(pond_id):
    """Get feeding records for a specific pond."""
    feeds = list(feeding_repo.find({'pondId': pond_id}).sort('created_at', -1))
    out = [_normalize_feeding_doc(f) for f in feeds]
    return respond_success(out)


# =============================================================================
# API Blueprint Aliases
# =============================================================================

feeding_api_bp = Blueprint('feeding_api', __name__, url_prefix='/api')

@feeding_api_bp.route('/feeding', methods=['POST'])
@handle_errors
@require_auth
def api_create_feeding(auth_payload):
    return create_feeding_route(auth_payload)

@feeding_api_bp.route('/feeding', methods=['GET'])
@handle_errors
@require_auth
def api_list_feeding(auth_payload):
    return list_feeding_route(auth_payload)

@feeding_api_bp.route('/feeding/pond/<pond_id>', methods=['GET'])
@handle_errors
def api_feeding_by_pond(pond_id):
    return feeding_by_pond_route(pond_id)
