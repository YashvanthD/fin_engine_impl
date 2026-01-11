"""Fish routes for fish species management and analytics.

This module provides endpoints for:
- Fish species CRUD operations
- Fish batch management
- Fish analytics
"""
import logging
import zoneinfo
from datetime import datetime

from flask import Blueprint, request

from fin_server.dto.fish_dto import FishDTO
from fin_server.repository.mongo_helper import get_collection
from fin_server.utils import validation
from fin_server.utils.decorators import handle_errors, require_auth
from fin_server.utils.generator import generate_key
from fin_server.utils.helpers import respond_error, respond_success
from fin_server.utils.time_utils import get_time_date_dt

logger = logging.getLogger(__name__)

# Constants
IST_TZ = zoneinfo.ZoneInfo('Asia/Kolkata')

# Blueprint
fish_bp = Blueprint('fish', __name__, url_prefix='/fish')

# Repositories
fish_repo = get_collection('fish')
fish_analytics_repo = get_collection('fish_analytics')
fish_mapping_repo = get_collection('fish_mapping')
pond_event_repo = get_collection('pond_event')


# =============================================================================
# Helper Functions
# =============================================================================

def _generate_species_code(scientific_name, common_name):
    """Generate a species code from names."""
    base = ''
    if scientific_name:
        base = ''.join([c[0].upper() for c in scientific_name.split() if c])[:5]
    elif common_name:
        base = ''.join([c[0].upper() for c in common_name.split() if c])[:5]
    else:
        base = 'FSH'
    return f"{base}{generate_key(3)}"


def _check_duplicate_fish(fish_repo, scientific_name, common_name, species_code):
    """Check for duplicate fish by name or code."""
    duplicate_query = {"$or": []}
    if scientific_name:
        duplicate_query["$or"].append({"scientific_name": {"$regex": f"^{scientific_name}$", "$options": "i"}})
    if common_name:
        duplicate_query["$or"].append({"common_name": {"$regex": f"^{common_name}$", "$options": "i"}})
    if species_code:
        duplicate_query["$or"].append({"species_code": {"$regex": f"^{species_code}$", "$options": "i"}})

    if duplicate_query["$or"]:
        return fish_repo.find_one(duplicate_query)
    return None


def _get_mapped_fish_ids(account_key):
    """Get fish IDs mapped to an account."""
    mapping = fish_mapping_repo.find_one({'account_key': account_key})
    return mapping.get('fish_ids', []) if mapping else []


def _fish_to_dict(fish):
    """Convert fish document to dict format."""
    if not fish:
        return None

    fish = dict(fish)
    fish['id'] = str(fish.pop('_id', ''))

    # Convert datetime fields
    if 'created_at' in fish and hasattr(fish['created_at'], 'isoformat'):
        fish['created_at'] = fish['created_at'].isoformat()

    if 'batches' in fish:
        for batch in fish['batches']:
            date_val = batch.get('date_added')
            if date_val and hasattr(date_val, 'isoformat'):
                batch['date_added'] = date_val.isoformat()

    return fish


def _prepare_fish_ui(fish, analytics=None, pond_ids=None):
    """Prepare fish document for UI response."""
    try:
        fish_doc = dict(fish)
        if analytics is not None:
            fish_doc['analytics'] = analytics
        if pond_ids is not None:
            fish_doc['ponds'] = pond_ids

        fish_dto = FishDTO.from_doc(fish_doc)
        return fish_dto.to_ui()
    except Exception:
        if isinstance(fish, dict):
            fish['_id'] = str(fish.get('_id'))
            fish['id'] = fish.get('_id')
            if analytics is not None:
                fish['analytics'] = analytics
            if pond_ids is not None:
                fish['ponds'] = pond_ids
            return fish
        return None


def _get_analytics_params(args):
    """Extract analytics filter params from request args."""
    return {
        'min_age': args.get('min_age'),
        'max_age': args.get('max_age'),
        'avg_n': args.get('avg_n'),
        'min_weight': args.get('min_weight'),
        'max_weight': args.get('max_weight'),
    }


def _get_fish_ponds(account_key, species_id):
    """Get pond IDs where fish is present."""
    try:
        pond_events = pond_event_repo.find_many({
            'account_key': account_key,
            'species_code': species_id
        })
    except AttributeError:
        pond_events = list(pond_event_repo.find({
            'account_key': account_key,
            'species_code': species_id
        }))

    return list(set([e.get('pond_id') for e in pond_events if e.get('pond_id')]))


# =============================================================================
# Fish CRUD Endpoints
# =============================================================================

@fish_bp.route('/create', methods=['POST'])
@handle_errors
@require_auth
def create_fish_entity(auth_payload):
    """Create a new fish species entity."""
    logger.info('POST /fish/create called')
    data = request.get_json(force=True)

    # Validate
    ok, errors = validation.validate_fish_create(data)
    if not ok:
        return respond_error(errors, status=400)

    account_key = auth_payload.get('account_key')
    data['created_at'] = get_time_date_dt(include_time=True)
    overwrite = str(request.args.get('overwrite', 'false')).lower() == 'true'

    species_code = data.get('species_code')
    scientific_name = data.get('scientific_name', '').strip()
    common_name = data.get('common_name', '').strip()

    # Check for duplicates
    existing = _check_duplicate_fish(fish_repo, scientific_name, common_name, species_code)
    if existing and not overwrite:
        return respond_error(
            'Fish with the same scientific_name, common_name, or species_code already exists. Use overwrite=true to force.',
            status=409
        )

    # Generate species code if needed
    if not species_code:
        species_code = _generate_species_code(scientific_name, common_name)
        data['species_code'] = species_code

    # Build and persist entity
    fish_entity = data.copy()
    fish_entity['_id'] = species_code
    fish_entity['account_key'] = account_key

    try:
        fish_dto = FishDTO.from_request(fish_entity)
        fish_dto.save(repo=fish_repo, collection_name='fish', upsert=True)
    except Exception:
        fish_repo.create(fish_entity)

    # Add to mapping
    try:
        fish_mapping_repo.add_fish_to_account(account_key, species_code)
    except Exception:
        logger.exception('Failed to add fish to mapping')

    return respond_success({'species_id': species_code, 'species_code': species_code}, status=201)


@fish_bp.route('/', methods=['POST', 'PUT'], strict_slashes=False)
@handle_errors
@require_auth
def add_fish_batch(auth_payload):
    """Add a batch of fish to an existing species."""
    logger.info('POST/PUT /fish/ (batch) called')
    data = request.get_json(force=True)

    # Validate
    ok, errors = validation.validate_batch_add(data)
    if not ok:
        return respond_error(errors, status=400)

    account_key = auth_payload.get('account_key')
    species_code = data.get('species_code')
    count = int(data.get('count'))
    fish_age_in_month = int(data.get('fish_age_in_month'))

    if not species_code or not count or not fish_age_in_month:
        return respond_error('species_code, count, and fish_age_in_month are required.', status=400)

    # Verify fish exists
    fish_entity = fish_repo.find_one({'_id': species_code})
    if not fish_entity:
        return respond_error('Fish species not found. Please create the fish entity first.', status=404)

    # Update mapping
    try:
        fish_mapping_repo.add_fish_to_account(account_key, species_code)
    except Exception:
        logger.exception('Failed to add fish to mapping')

    # Add analytics event
    event_id = f"{account_key}-{species_code}-{generate_key(9)}"
    fish_weight = data.get('fish_weight')
    base_dt = get_time_date_dt(include_time=True)

    fish_analytics_repo.add_batch(
        species_code, count, fish_age_in_month, base_dt,
        account_key=account_key, event_id=event_id, fish_weight=fish_weight
    )

    return respond_success({'species_id': species_code, 'event_id': event_id}, status=201)


@fish_bp.route('/<species_id>', methods=['GET'])
@handle_errors
@require_auth
def get_fish_by_id(species_id, auth_payload):
    """Get a fish species with analytics and pond info."""
    account_key = auth_payload.get('account_key')

    # Check mapping
    fish_ids = _get_mapped_fish_ids(account_key)
    if species_id not in fish_ids:
        return respond_error('This fish is not present in your farm.', status=404)

    fish = fish_repo.find_one({'_id': species_id})
    if not fish:
        return respond_error('Fish not found', status=404)

    # Get analytics
    analytics_params = _get_analytics_params(request.args)
    analytics = fish_analytics_repo.get_analytics(species_id, account_key=account_key, **analytics_params)

    # Get ponds
    pond_ids = _get_fish_ponds(account_key, species_id)

    return respond_success({'fish': _prepare_fish_ui(fish, analytics, pond_ids)})


@fish_bp.route('/', methods=['GET'])
@handle_errors
@require_auth
def get_fish(auth_payload):
    """Get all fish for the current account with analytics."""
    logger.debug('GET /fish/ called')

    account_key = auth_payload.get('account_key')
    query = request.args.to_dict()

    # Get mapped fish
    fish_ids = _get_mapped_fish_ids(account_key)
    if not fish_ids:
        return respond_success({'fish': []})

    mongo_query = {'_id': {'$in': fish_ids}}

    # Date range filter
    from_date = query.get('from_date')
    to_date = query.get('to_date')
    if from_date or to_date:
        date_filter = {}
        if from_date:
            date_filter['$gte'] = datetime.fromisoformat(from_date)
        if to_date:
            date_filter['$lte'] = datetime.fromisoformat(to_date)
        mongo_query['created_at'] = date_filter

    # Numeric filters
    for field in ['size', 'weight', 'count']:
        min_val = query.get(f'min_{field}')
        max_val = query.get(f'max_{field}')
        if min_val or max_val:
            num_filter = {}
            if min_val:
                num_filter['$gte'] = float(min_val)
            if max_val:
                num_filter['$lte'] = float(max_val)
            mongo_query[field] = num_filter

    # Direct field matches
    for field in ['common_name', 'scientific_name', 'species_code']:
        if field in query:
            mongo_query[field] = {"$eq": query[field]}

    fish_list = fish_repo.find(mongo_query)
    analytics_params = _get_analytics_params(query)

    result = []
    for f in fish_list:
        species_id = f.get('_id')
        analytics = fish_analytics_repo.get_analytics(species_id, account_key=account_key, **analytics_params)

        # Age filter
        min_age = analytics_params.get('min_age')
        max_age = analytics_params.get('max_age')
        if min_age or max_age:
            age_analytics = analytics.get('age_analytics', {})
            match = any(
                (not min_age or int(age) >= int(min_age)) and (not max_age or int(age) <= int(max_age))
                for age in age_analytics.keys()
            )
            if not match:
                continue

        f['analytics'] = analytics

        try:
            fdto = FishDTO.from_doc(f)
            fdto.extra['analytics'] = analytics
            result.append(fdto.to_ui())
        except Exception:
            result.append(_fish_to_dict(f))

    logger.info('GET /fish/ returning %d fish records', len(result))
    return respond_success({'fish': result})


@fish_bp.route('/<species_id>', methods=['PUT'])
@handle_errors
@require_auth
def update_fish(species_id, auth_payload):
    """Update a fish species and optionally add a batch."""
    logger.info('PUT /fish/%s called', species_id)

    account_key = auth_payload.get('account_key')
    data = request.get_json(force=True)

    # Validate
    ok, errors = validation.validate_fish_update_payload(data)
    if not ok:
        return respond_error(errors, status=400)

    # Extract batch fields
    count = data.pop('count', None)
    fish_age_in_month = data.pop('fish_age_in_month', None)
    fish_weight = data.pop('fish_weight', None)

    # Update fish entity
    update_fields = {k: v for k, v in data.items() if k}
    if update_fields:
        fish_repo.update({'_id': species_id}, update_fields)

    # Add batch if provided
    if count is not None and fish_age_in_month is not None:
        fish_entity = fish_repo.find_one({'_id': species_id})
        if not fish_entity:
            return respond_error('Fish species not found.', status=404)

        fish_mapping_repo.update_one(
            {'account_key': account_key},
            {'$addToSet': {'fish_ids': species_id}},
            upsert=True
        )

        event_id = f"{account_key}-{species_id}-{generate_key(9)}"
        base_dt = get_time_date_dt(include_time=True)

        fish_analytics_repo.add_batch(
            species_id, int(count), int(fish_age_in_month), base_dt,
            account_key=account_key, event_id=event_id, fish_weight=fish_weight
        )

        return respond_success({'species_id': species_id, 'event_id': event_id})

    return respond_success({'species_id': species_id})


# =============================================================================
# Analytics Endpoints
# =============================================================================

@fish_bp.route('/analytics', methods=['GET'])
@handle_errors
@require_auth
def get_fish_analytics(auth_payload):
    """Get analytics for all mapped fish."""
    account_key = auth_payload.get('account_key')
    species_code = request.args.get('species_code')
    analytics_params = _get_analytics_params(request.args)

    fish_ids = _get_mapped_fish_ids(account_key)

    if species_code:
        if species_code not in fish_ids:
            return respond_error('This fish is not present in your farm.', status=404)
        analytics = fish_analytics_repo.get_analytics(species_code, account_key=account_key, **analytics_params)
        return respond_success({'analytics': [{'species_code': species_code, 'analytics': analytics}]})

    result = [
        {
            'species_code': sid,
            'analytics': fish_analytics_repo.get_analytics(sid, account_key=account_key, **analytics_params)
        }
        for sid in fish_ids
    ]

    return respond_success({'analytics': result})


@fish_bp.route('/<species_id>/analytics', methods=['GET'])
@handle_errors
@require_auth
def get_fish_analytics_by_id(species_id, auth_payload):
    """Get analytics for a specific fish species."""
    account_key = auth_payload.get('account_key')

    fish_ids = _get_mapped_fish_ids(account_key)
    if species_id not in fish_ids:
        return respond_error('This fish is not present in your farm.', status=404)

    analytics_params = _get_analytics_params(request.args)
    analytics = fish_analytics_repo.get_analytics(species_id, account_key=account_key, **analytics_params)

    return respond_success({'species_code': species_id, 'analytics': analytics})


# =============================================================================
# Metadata Endpoints
# =============================================================================

@fish_bp.route('/fields', methods=['GET'])
@handle_errors
@require_auth
def get_fish_fields(auth_payload):
    """Get available fish fields."""
    fields = fish_repo.get_fields()
    return respond_success({'fields': list(fields)})


@fish_bp.route('/distinct/<field>', methods=['GET'])
@handle_errors
@require_auth
def get_fish_distinct(field, auth_payload):
    """Get distinct values for a field."""
    values = fish_repo.get_distinct_values(field)
    return respond_success({'field': field, 'values': values})


@fish_bp.route('/stats/<field>', methods=['GET'])
@handle_errors
@require_auth
def get_fish_stats(field, auth_payload):
    """Get statistics for a field."""
    stats = fish_repo.get_field_stats(field)
    return respond_success({'field': field, 'stats': stats})
