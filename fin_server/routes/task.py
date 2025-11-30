from flask import Blueprint, request, jsonify
from fin_server.repository.task_repository import task_repository
from fin_server.security.authentication import AuthSecurity
import logging
import time


task_bp = Blueprint('task', __name__, url_prefix='/task')

@task_bp.route('/', methods=['POST'])
def create_task():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        user_key = payload.get('user_key')
        data = request.get_json(force=True)
        remind_before = data.get('remind_before', 30)  # minutes before, default 30
        task_data = {
            'userkey': user_key,
            'title': data.get('title'),
            'description': data.get('description', ''),
            'status': data.get('status', 'pending'),
            'end_date': data.get('end_date'),
            'task_date': data.get('task_date'),
            'priority': data.get('priority', 'normal'),
            'notes': data.get('notes', ''),
            'recurring': data.get('recurring', 'once'),  # once, daily, weekly, monthly, yearly
            'reminder': data.get('reminder', False), # boolean for reminder
            'reminder_time': data.get('reminder_time', ''), # time for reminder
            'remind_before': remind_before # minutes before reminder, default 30
        }
        task_id = task_repository.create_task(task_data)
        return jsonify({'success': True, 'task_id': task_id}), 201
    except Exception as e:
        logging.exception("Error in create_task")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@task_bp.route('/', methods=['GET'])
def get_tasks():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        user_key = payload.get('user_key')
        tasks = task_repository.get_tasks_by_user(user_key)
        now = 1764556800  # 2025-12-01 epoch
        meta = {
            'pending': 0,
            'inprogress': 0,
            'completed': 0,
            'overdue': 0,
            'critical': 0,
            'read': 0,
            'unread': 0
        }
        task_objs = []
        for t in tasks:
            t['_id'] = str(t['_id'])
            # Add viewed field if missing
            if 'viewed' not in t:
                t['viewed'] = False
            # Status counts
            status = t.get('status', '').lower()
            if status == 'pending':
                meta['pending'] += 1
            elif status == 'inprogress':
                meta['inprogress'] += 1
            elif status == 'completed':
                meta['completed'] += 1
            # Overdue: if not completed and end_date < now
            end_date = t.get('end_date')
            if status != 'completed' and end_date:
                try:
                    end_epoch = int(time.mktime(time.strptime(end_date, '%Y-%m-%d')))
                    if end_epoch < now:
                        meta['overdue'] += 1
                except Exception:
                    pass
            # Critical: priority == 'high'
            if t.get('priority', '').lower() == 'high':
                meta['critical'] += 1
            # Read/unread: viewed field
            if t['viewed']:
                meta['read'] += 1
            else:
                meta['unread'] += 1
            task_objs.append(t)
        return jsonify({'success': True, 'meta': meta, 'tasks': task_objs}), 200
    except Exception as e:
        logging.exception("Error in get_tasks")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@task_bp.route('/<task_id>', methods=['PUT'])
def update_task(task_id):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        user_key = payload.get('user_key')
        data = request.get_json(force=True)
        update_fields = {k: v for k, v in data.items() if k in ['title', 'description', 'status', 'end_date', 'task_date', 'priority', 'notes', 'recurring', 'reminder', 'reminder_time', 'remind_before']}
        updated = task_repository.update_task(task_id, update_fields)
        return jsonify({'success': True, 'updated': bool(updated)}), 200
    except Exception as e:
        logging.exception("Error in update_task")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@task_bp.route('/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        user_key = payload.get('user_key')
        deleted = task_repository.delete_task(task_id)
        return jsonify({'success': True, 'deleted': bool(deleted)}), 200
    except Exception as e:
        logging.exception("Error in delete_task")
        return jsonify({'success': False, 'error': 'Server error'}), 500
