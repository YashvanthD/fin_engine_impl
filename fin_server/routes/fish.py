from flask import Blueprint, request, jsonify
from pymongo import MongoClient
from bson import ObjectId
from fin_server.repository.fish_repository import FishRepository
from fin_server.utils.generator import generate_key
import os

fish_bp = Blueprint('fish', __name__, url_prefix='/fish')

# Setup MongoDB connection
mongo_client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017/'))
db = mongo_client['fin_db']
fish_repository = FishRepository(db)

# Helper to convert ObjectId to string

def fish_to_dict(fish):
    if not fish:
        return None
    fish = dict(fish)
    fish['id'] = str(fish.pop('_id'))
    return fish

@fish_bp.route('/', methods=['POST'])
def create_fish():
    data = request.get_json(force=True)
    # Only require a few important fields, allow dynamic others
    required = ['common_name', 'scientific_name', 'species_code', 'count', 'length', 'weight', 'account_key']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'success': False, 'error': f'Missing fields: {missing}'}), 400
    # Generate 5-digit fish_id
    data['fish_id'] = generate_key(5)
    try:
        result = fish_repository.create_fish(data)
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    return jsonify({'success': True, 'id': str(result.inserted_id), 'fish_id': data['fish_id']}), 201

@fish_bp.route('/<fish_id>', methods=['GET'])
def get_fish(fish_id):
    fish = fish_repository.get_fish(ObjectId(fish_id))
    if not fish:
        return jsonify({'success': False, 'error': 'Fish not found'}), 404
    return jsonify({'success': True, 'fish': fish_to_dict(fish)}), 200

@fish_bp.route('/<fish_id>', methods=['PUT'])
def update_fish(fish_id):
    data = request.get_json(force=True)
    result = fish_repository.update_fish(ObjectId(fish_id), data)
    if result.matched_count == 0:
        return jsonify({'success': False, 'error': 'Fish not found'}), 404
    return jsonify({'success': True, 'updated': True}), 200

@fish_bp.route('/<fish_id>', methods=['DELETE'])
def delete_fish(fish_id):
    result = fish_repository.delete_fish(ObjectId(fish_id))
    if result.deleted_count == 0:
        return jsonify({'success': False, 'error': 'Fish not found'}), 404
    return jsonify({'success': True, 'deleted': True}), 200

@fish_bp.route('/', methods=['GET'])
def list_fish():
    account_key = request.args.get('account_key')
    if not account_key:
        return jsonify({'success': False, 'error': 'account_key required'}), 400
    fish_list = fish_repository.list_fish_by_account(account_key)
    return jsonify({'success': True, 'fish': [fish_to_dict(f) for f in fish_list]}), 200
