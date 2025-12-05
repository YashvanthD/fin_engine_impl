from flask import Blueprint, request, jsonify
from pymongo import MongoClient
from bson import ObjectId
from fin_server.repository.pond_repository import PondRepository
from fin_server.repository.pond_event_repository import PondEventRepository
from fin_server.utils.generator import generate_key
from fin_server.security.authentication import AuthSecurity, UnauthorizedError
import os

pond_bp = Blueprint('pond', __name__, url_prefix='/pond')

# Setup MongoDB connection
mongo_client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017/'))
db = mongo_client['fin_db']
pond_repository = PondRepository(db)
pond_event_repository = PondEventRepository(db)

# Helper to convert ObjectId to string

def pond_to_dict(pond):
    if not pond:
        return None
    pond = dict(pond)
    pond['id'] = str(pond.pop('_id'))
    return pond

def get_auth_payload():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise UnauthorizedError('Missing or invalid token')
    token = auth_header.split(' ', 1)[1]
    return AuthSecurity.decode_token(token)

@pond_bp.route('/', methods=['POST'])
def create_pond():
    try:
        payload = get_auth_payload()
        data = request.get_json(force=True)
        required = ['pond_name', 'location', 'size', 'water_type', 'account_key']
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({'success': False, 'error': f'Missing fields: {missing}'}), 400
        # Generate pond_id as 'accountkey-XXX' (3 digits)
        short_id = generate_key(3)
        data['pond_id'] = f"{data['account_key']}-{short_id}"
        result = pond_repository.create_pond(data)
        return jsonify({'success': True, 'id': str(result.inserted_id), 'pond_id': data['pond_id']}), 201
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500

@pond_bp.route('/<pond_id>', methods=['GET'])
def get_pond(pond_id):
    try:
        payload = get_auth_payload()
        pond = pond_repository.get_pond(ObjectId(pond_id))
        if not pond:
            return jsonify({'success': False, 'error': 'Pond not found'}), 404
        # Get all events for this pond
        events = pond_event_repository.get_events_by_pond(pond.get('pond_id'))
        # Basic analytics: total fish by type
        analytics = get_pond_analytics(events)
        return jsonify({'success': True, 'pond': pond_to_dict(pond), 'events': events, 'analytics': analytics}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500

@pond_bp.route('/<pond_id>', methods=['PUT'])
def update_pond(pond_id):
    try:
        payload = get_auth_payload()
        data = request.get_json(force=True)
        result = pond_repository.update_pond(ObjectId(pond_id), data)
        if result.matched_count == 0:
            return jsonify({'success': False, 'error': 'Pond not found'}), 404
        return jsonify({'success': True, 'updated': True}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500

@pond_bp.route('/<pond_id>', methods=['DELETE'])
def delete_pond(pond_id):
    try:
        payload = get_auth_payload()
        result = pond_repository.delete_pond(ObjectId(pond_id))
        if result.deleted_count == 0:
            return jsonify({'success': False, 'error': 'Pond not found'}), 404
        return jsonify({'success': True, 'deleted': True}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500

@pond_bp.route('/', methods=['GET'])
def list_ponds():
    try:
        payload = get_auth_payload()
        query = request.args.to_dict()
        pond_list = pond_repository.list_ponds(query)
        return jsonify({'success': True, 'ponds': [pond_to_dict(p) for p in pond_list]}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500

# Pond event CRUD
@pond_bp.route('/<pond_id>/event', methods=['POST'])
def add_pond_event(pond_id):
    try:
        payload = get_auth_payload()
        data = request.get_json(force=True)
        data['pond_id'] = pond_id
        # Example required: fish_id, action (add/remove), count, date
        required = ['fish_id', 'action', 'count', 'date']
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({'success': False, 'error': f'Missing fields: {missing}'}), 400
        result = pond_event_repository.add_event(data)
        return jsonify({'success': True, 'event_id': str(result.inserted_id)}), 201
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500

@pond_bp.route('/<pond_id>/events', methods=['GET'])
def list_pond_events(pond_id):
    try:
        payload = get_auth_payload()
        events = pond_event_repository.get_events_by_pond(pond_id)
        return jsonify({'success': True, 'events': events}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500

# Analytics helper

def get_pond_analytics(events):
    # Example: total fish by type
    fish_stats = {}
    for event in events:
        fish_id = event.get('fish_id')
        count = int(event.get('count', 0))
        action = event.get('action')
        if fish_id not in fish_stats:
            fish_stats[fish_id] = 0
        if action == 'add':
            fish_stats[fish_id] += count
        elif action == 'remove':
            fish_stats[fish_id] -= count
    return {'total_fish_by_type': fish_stats}
