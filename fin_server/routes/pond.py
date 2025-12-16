from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone
from fin_server.repository.pond_repository import PondRepository
from fin_server.security.authentication import get_auth_payload
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
        # Insert pond entity
        pond_entity = data.copy()
        pond_entity['_id'] = pond_id
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
        result = pond_repository.update({'pond_id': pond_id}, update_fields)
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

        pond = pond_repository.get_pond(pond_id)
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
        result = pond_repository.update({'pond_id': pond_id}, data)
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
        result = pond_repository.delete({'pond_id': pond_id})
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
        payload = get_auth_payload(request)
        # Build filter from query params
        query = request.args.to_dict()
        # Always restrict by account_key from token
        query['account_key'] = payload.get('account_key')
        pond_list = pond_repository.find(query)
        return jsonify({'success': True, 'ponds': [pond_to_dict(p) for p in pond_list]}), 200
    except UnauthorizedError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500
