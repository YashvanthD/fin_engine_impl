from flask import Blueprint, request, jsonify, current_app
from fin_server.repository.pond_event_repository import PondEventRepository
from fin_server.repository.pond_repository import PondRepository
from fin_server.repository.fish_analytics_repository import FishAnalyticsRepository
from fin_server.repository.mongo_helper import MongoRepositorySingleton
from fin_server.security.authentication import AuthSecurity, UnauthorizedError
from bson import ObjectId
from datetime import datetime, timezone

pond_event_bp = Blueprint('pond_event', __name__, url_prefix='/pond_event')

pond_event_repository = PondEventRepository()
pond_repository = PondRepository()
fish_analytics_repository = FishAnalyticsRepository()
fish_mapping_repo = MongoRepositorySingleton.get_instance().fish_mapping

def get_auth_payload():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise UnauthorizedError('Missing or invalid token')
    token = auth_header.split(' ', 1)[1]
    return AuthSecurity.decode_token(token)

def update_pond_metadata(pond_id, fish_id, count, event_type):
    pond = pond_repository.get_pond(pond_id)
    if not pond:
        return
    meta = pond.get('metadata', {})
    fish_types = meta.get('fish_types', {})
    total_fish = meta.get('total_fish', 0)
    # Update fish_types and total_fish based on event_type
    if event_type in ['add', 'shift_in']:
        fish_types[fish_id] = fish_types.get(fish_id, 0) + count
        total_fish += count
    elif event_type in ['remove', 'sell', 'sample', 'shift_out']:
        fish_types[fish_id] = max(0, fish_types.get(fish_id, 0) - count)
        total_fish = max(0, total_fish - count)
    # Clean up zero-count fish
    fish_types = {k: v for k, v in fish_types.items() if v > 0}
    meta['fish_types'] = fish_types
    meta['total_fish'] = total_fish
    meta['last_activity'] = {
        'event_type': event_type,
        'fish_id': fish_id,
        'count': count,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    pond_repository.update({'pond_id': pond_id}, {'metadata': meta})

def update_fish_analytics_and_mapping(account_key, fish_id, count, event_type, fish_age_in_month=None, pond_id=None):
    # Always ensure mapping exists
    fish_mapping_repo.update_one(
        {'account_key': account_key},
        {'$addToSet': {'fish_ids': fish_id}},
        upsert=True
    )
    # For add/shift_in: add a batch; for remove/sell/sample/shift_out: add negative batch
    event_id = f"{account_key}-{fish_id}-{pond_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    if event_type in ['add', 'shift_in']:
        fish_analytics_repository.add_batch(
            fish_id, int(count), int(fish_age_in_month) if fish_age_in_month is not None else 0,
            datetime.now(timezone.utc), account_key=account_key, event_id=event_id
        )
    elif event_type in ['remove', 'sell', 'sample', 'shift_out']:
        # Store as negative batch for analytics
        fish_analytics_repository.add_batch(
            fish_id, -int(count), int(fish_age_in_month) if fish_age_in_month is not None else 0,
            datetime.now(timezone.utc), account_key=account_key, event_id=event_id
        )

@pond_event_bp.route('/<pond_id>/event/<event_type>', methods=['POST'])
def pond_event_action(pond_id, event_type):
    """
    Supported event_type: add, sell, sample, remove, shift_in, shift_out
    """
    current_app.logger.debug(f'POST /pond_event/{pond_id}/event/{event_type} called')
    try:
        payload = get_auth_payload()
        data = request.get_json(force=True)
        fish_id = data.get('fish_id')
        count = int(data.get('count', 0))
        fish_age_in_month = data.get('fish_age_in_month')
        if not fish_id or count <= 0:
            return jsonify({'success': False, 'error': 'fish_id and positive count required'}), 400
        # Log event
        event_doc = {
            'pond_id': pond_id,
            'fish_id': fish_id,
            'count': count,
            'event_type': event_type,
            'details': data.get('details', {}),
            'created_at': datetime.now(timezone.utc),
            'user_key': payload.get('user_key')
        }
        if fish_age_in_month is not None:
            event_doc['fish_age_in_month'] = fish_age_in_month
        result = pond_event_repository.create(event_doc)
        # Update pond metadata
        update_pond_metadata(pond_id, fish_id, count, event_type)
        # Update fish analytics and mapping
        account_key = payload.get('account_key')
        update_fish_analytics_and_mapping(account_key, fish_id, count, event_type, fish_age_in_month, pond_id)
        return jsonify({'success': True, 'event_id': str(result.inserted_id)}), 201
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        current_app.logger.exception(f'Exception in pond_event_action: {e}')
        return jsonify({'success': False, 'error': 'Server error'}), 500

@pond_event_bp.route('/<pond_id>/events', methods=['GET'])
def get_pond_events(pond_id):
    current_app.logger.debug('GET /pond_event/%s/events called', pond_id)
    try:
        payload = get_auth_payload()
        events = pond_event_repository.get_events_by_pond(pond_id)
        return jsonify({'success': True, 'events': events}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500

@pond_event_bp.route('/<pond_id>/events/<event_id>', methods=['DELETE'])
def delete_pond_event(pond_id, event_id):
    current_app.logger.debug('DELETE /pond_event/%s/events/%s called', pond_id, event_id)
    try:
        payload = get_auth_payload()
        result = pond_event_repository.delete(ObjectId(event_id))
        if result.deleted_count == 0:
            return jsonify({'success': False, 'error': 'Event not found'}), 404
        return jsonify({'success': True, 'deleted': True}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500
