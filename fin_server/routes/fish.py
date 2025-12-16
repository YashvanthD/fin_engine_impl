from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone

from fin_server.exception.UnauthorizedError import UnauthorizedError
from fin_server.repository.fish_repository import FishRepository
from fin_server.repository.fish_analytics_repository import FishAnalyticsRepository
from fin_server.repository.mongo_helper import MongoRepositorySingleton

from fin_server.security.authentication import get_auth_payload
from fin_server.utils.generator import generate_key

fish_bp = Blueprint('fish', __name__, url_prefix='/fish')
fish_repository = FishRepository()
fish_analytics_repository = FishAnalyticsRepository()
fish_mapping_repo = MongoRepositorySingleton.get_instance().fish_mapping

@fish_bp.route('/create', methods=['POST'])
def create_fish_entity():
    current_app.logger.info('POST /fish/create called')
    try:
        payload = get_auth_payload(request)
        data = request.get_json(force=True)
        account_key = payload.get('account_key')
        data.pop('account_key', None)
        data['created_at'] = datetime.now(timezone.utc)
        overwrite = str(request.args.get('overwrite', 'false')).lower() == 'true'
        # Generate species_code if not provided
        species_code = data.get('species_code')
        sci = data.get('scientific_name', '').strip()
        com = data.get('common_name', '').strip()
        # Check for duplicate scientific_name or common_name or species_code
        duplicate_query = {"$or": []}
        if sci:
            duplicate_query["$or"].append({"scientific_name": {"$regex": f"^{sci}$", "$options": "i"}})
        if com:
            duplicate_query["$or"].append({"common_name": {"$regex": f"^{com}$", "$options": "i"}})
        if species_code:
            duplicate_query["$or"].append({"species_code": {"$regex": f"^{species_code}$", "$options": "i"}})
        if duplicate_query["$or"]:
            existing = fish_repository.find_one(duplicate_query)
            if existing and not overwrite:
                return jsonify({'success': False, 'error': 'Fish with the same scientific_name, common_name, or species_code already exists. Use overwrite=true to force.'}), 409
        if not species_code:
            base = ''
            if sci:
                base = ''.join([c[0].upper() for c in sci.split() if c])[:5]
            elif com:
                base = ''.join([c[0].upper() for c in com.split() if c])[:5]
            else:
                base = 'FSH'
            species_code = f"{base}{generate_key(3)}"
            data['species_code'] = species_code
        species_id = species_code
        # Insert or update fish entity by species_id
        fish_entity = data.copy()
        fish_entity['_id'] = species_id
        if hasattr(fish_repository, 'create_or_update'):
            fish_repository.create_or_update(fish_entity)
        else:
            fish_repository.create(fish_entity)
        # Store mapping in fish_mapping
        fish_mapping_repo.update_one(
            {'account_key': account_key},
            {'$addToSet': {'fish_ids': species_id}},
            upsert=True
        )
        return jsonify({'success': True, 'species_id': species_id, 'species_code': species_code}), 201
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        current_app.logger.exception(f'Exception in create_fish_entity: {e}')
        return jsonify({'success': False, 'error': 'Server error'}), 500

@fish_bp.route('/', methods=['POST', 'PUT'])
def add_fish_batch():
    current_app.logger.info('POST/PUT /fish/ (batch) called')
    try:
        payload = get_auth_payload(request)
        data = request.get_json(force=True)
        account_key = payload.get('account_key')
        species_code = data.get('species_code')
        count = data.get('count')
        fish_age_in_month = data.get('fish_age_in_month')
        if not species_code or not count or not fish_age_in_month:
            return jsonify({'success': False, 'error': 'species_code, count, and fish_age_in_month are required.'}), 400
        # Check if fish entity exists
        fish_entity = fish_repository.find_one({'_id': species_code})
        if not fish_entity:
            return jsonify({'success': False, 'error': 'Fish species not found. Please create the fish entity first.'}), 404
        # Always update mapping: add fish to mapping if not present (fresh addition to farm)
        fish_mapping_repo.update_one(
            {'account_key': account_key},
            {'$addToSet': {'fish_ids': species_code}},
            upsert=True
        )
        # Add analytics event (always, even if mapping was missing before)
        event_id = f"{account_key}-{species_code}-{generate_key(9)}"
        fish_analytics_repository.add_batch(
            species_code, int(count), int(fish_age_in_month), datetime.now(timezone.utc), account_key=account_key, event_id=event_id
        )
        return jsonify({'success': True, 'species_id': species_code, 'event_id': event_id}), 201
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        current_app.logger.exception(f'Exception in add_fish_batch: {e}')
        return jsonify({'success': False, 'error': 'Server error'}), 500

@fish_bp.route('/<species_id>', methods=['GET'])
def get_fish_by_id(species_id):
    """
    Retrieve a fish entity and its analytics for the current user's account_key.
    If the fish is not mapped to the user's account (not present in their farm),
    return a clear error message.
    """
    try:
        payload = get_auth_payload(request)
        account_key = payload.get('account_key')
        # Check if fish is mapped to this account_key
        mapping = fish_mapping_repo.find_one({'account_key': account_key})
        fish_ids = mapping.get('fish_ids', []) if mapping else []
        if species_id not in fish_ids:
            return jsonify({'success': False, 'error': 'This fish is not present in your farm (not mapped to your account_key).'}), 404
        fish = fish_repository.find_one({'_id': species_id})
        if not fish:
            return jsonify({'success': False, 'error': 'Fish not found'}), 404
        analytics = fish_analytics_repository.get_analytics(species_id, account_key=account_key)
        fish.update({'analytics': analytics})
        return jsonify({'success': True, 'fish': fish_to_dict(fish)}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        current_app.logger.exception(f'Exception in get_fish_by_id: {e}')
        return jsonify({'success': False, 'error': 'Server error'}), 500

@fish_bp.route('/', methods=['GET'])
def get_fish():
    """Get all fish for the current account_key, with analytics."""
    try:
        payload = get_auth_payload(request)
        query = request.args.to_dict()
        account_key = payload.get('account_key')
        mapping = fish_mapping_repo.find_one({'account_key': account_key})
        fish_ids = mapping.get('fish_ids', []) if mapping else []
        if not fish_ids:
            return jsonify({'success': True, 'fish': []}), 200
        mongo_query = {'_id': {'$in': fish_ids}}
        # Date range filter (created_at)
        from_date = query.get('from_date')
        to_date = query.get('to_date')
        if from_date or to_date:
            date_filter = {}
            if from_date:
                from datetime import datetime
                date_filter['$gte'] = datetime.fromisoformat(from_date)
            if to_date:
                from datetime import datetime
                date_filter['$lte'] = datetime.fromisoformat(to_date)
            mongo_query['created_at'] = date_filter
        # Numeric filters (size, weight, count)
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
        # Direct field match (common_name, scientific_name, species_code, etc.)
        for field in ['common_name', 'scientific_name', 'species_code']:
            if field in query:
                mongo_query[field] = {"$eq": query[field]}
        fish_list = fish_repository.find(mongo_query)
        # Join analytics for each fish
        result = []
        min_age = query.get('min_age')
        max_age = query.get('max_age')
        for f in fish_list:
            species_id = f['_id']
            analytics = fish_analytics_repository.get_analytics(species_id, account_key=account_key)
            # Post-filter by age_analytics if needed
            if min_age or max_age:
                age_analytics = analytics.get('age_analytics', {})
                match = False
                for age, count in age_analytics.items():
                    if (not min_age or age >= int(min_age)) and (not max_age or age <= int(max_age)):
                        match = True
                        break
                if not match:
                    continue
            f.update({'analytics': analytics})
            result.append(fish_to_dict(f))
        return jsonify({'success': True, 'fish': result}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500

def fish_to_dict(fish):
    if not fish:
        return None
    fish = dict(fish)
    fish['id'] = str(fish.pop('_id'))
    # Optionally convert datetime fields to isoformat
    if 'created_at' in fish and hasattr(fish['created_at'], 'isoformat'):
        fish['created_at'] = fish['created_at'].isoformat()
    if 'batches' in fish:
        for batch in fish['batches']:
            date_val = batch.get('date_added')
            if date_val and not isinstance(date_val, str) and hasattr(date_val, 'isoformat'):
                batch['date_added'] = date_val.isoformat()
    if 'metadata' in fish and isinstance(fish['metadata'], dict):
        # age_analytics is already calculated
        pass
    return fish
