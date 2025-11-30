from flask import Blueprint, request, jsonify
from fin_server.repository.task_repository import task_repository
from fin_server.repository.user_repository import mongo_db_repository
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
        roles = payload.get('roles', [])
        data = request.get_json(force=True)
        remind_before = data.get('remind_before', 30)
        assigned_to = data.get('assigned_to', user_key)
        # Admin can assign to any user, others only to themselves
        if assigned_to != user_key:
            if 'admin' not in roles:
                return jsonify({'success': False, 'error': 'Only admin can assign tasks to other users'}), 403
            assigned_user = mongo_db_repository.find_one('users', {'user_key': assigned_to})
            if not assigned_user:
                return jsonify({'success': False, 'error': 'Assigned user does not exist'}), 404
        # Default fields
        task_data = {
            'userkey': user_key,
            'reporter': user_key,
            'assignee': assigned_to,
            'assigned_to': assigned_to,
            'title': data.get('title'),
            'description': data.get('description', ''),
            'status': data.get('status', 'pending'),
            'end_date': data.get('end_date'),
            'task_date': data.get('task_date'),
            'priority': data.get('priority', 'normal'),
            'notes': data.get('notes', ''),
            'recurring': data.get('recurring', 'once'),
            'reminder': data.get('reminder', False),
            'reminder_time': data.get('reminder_time', ''),
            'remind_before': remind_before,
            'history': [],
            'comments': [],
            'tags': [],
            'viewed': False
        }
        # Merge any extra fields for flexibility
        for k, v in data.items():
            if k not in task_data:
                task_data[k] = v
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
        now = int(time.time())  # Current timestamp
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
        roles = payload.get('roles', [])
        data = request.get_json(force=True)
        # Accept all fields for flexibility
        update_fields = dict(data)
        task = task_repository.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        # If assignee/assigned_to is being changed, check permissions and update history
        new_assignee = update_fields.get('assignee') or update_fields.get('assigned_to')
        if new_assignee and new_assignee != task.get('assignee', task.get('assigned_to')):
            if new_assignee != user_key:
                if 'admin' not in roles:
                    admin_user = mongo_db_repository.find_one('users', {'roles': {'$in': ['admin']}})
                    if not admin_user or new_assignee != admin_user['user_key'] or task.get('assignee', task.get('assigned_to')) != user_key:
                        return jsonify({'success': False, 'error': 'Only admin can assign to other users, or user can reassign their own task to admin'}), 403
            history = task.get('history', [])
            history.append({
                'from': task.get('assignee', task.get('assigned_to')),
                'to': new_assignee,
                'by': user_key,
                'timestamp': int(time.time())
            })
            update_fields['history'] = history
            update_fields['assignee'] = new_assignee
            update_fields['assigned_to'] = new_assignee
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

@task_bp.route('/<task_id>/move', methods=['POST'])
def move_task(task_id):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        user_key = payload.get('user_key')
        roles = payload.get('roles', [])
        data = request.get_json(force=True)
        new_assignee = data.get('new_assignee')
        if not new_assignee:
            return jsonify({'success': False, 'error': 'Missing new_assignee'}), 400
        task = task_repository.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        # Only admin or current assignee can move the task
        if 'admin' not in roles and user_key != task.get('assignee', task.get('assigned_to')):
            return jsonify({'success': False, 'error': 'Permission denied'}), 403
        # Check if new assignee exists
        assigned_user = mongo_db_repository.find_one('users', {'user_key': new_assignee})
        if not assigned_user:
            return jsonify({'success': False, 'error': 'New assignee does not exist'}), 404
        # Update assignee and history
        history = task.get('history', [])
        history.append({
            'from': task.get('assignee', task.get('assigned_to')),
            'to': new_assignee,
            'by': user_key,
            'timestamp': int(time.time())
        })
        update_fields = {
            'assignee': new_assignee,
            'assigned_to': new_assignee,
            'history': history
        }
        updated = task_repository.update_task(task_id, update_fields)
        return jsonify({'success': True, 'updated': bool(updated)}), 200
    except Exception as e:
        logging.exception("Error in move_task")
        return jsonify({'success': False, 'error': 'Server error'}), 500
