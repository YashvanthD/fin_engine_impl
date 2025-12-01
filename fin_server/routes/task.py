from flask import Blueprint, request, jsonify
from fin_server.repository.task_repository import task_repository
from fin_server.repository.user_repository import mongo_db_repository
from fin_server.security.authentication import AuthSecurity
from fin_server.utils.generator import resolve_user, get_default_task_date, get_default_end_date
from pytz import timezone
import logging
import time
from datetime import datetime


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
        account_key = payload.get('account_key')
        roles = payload.get('roles', [])
        data = request.get_json(force=True)
        remind_before = data.get('remind_before', 30)
        assigned_to_input = data.get('assigned_to')
        # If assigned_to not provided, default to self-assignment
        if not assigned_to_input:
            assigned_to_input = user_key
        # Resolve assigned_to to user object
        if assigned_to_input == user_key:
            assigned_user = mongo_db_repository.find_one('users', {'user_key': user_key, 'account_key': account_key})
        else:
            assigned_user = resolve_user(assigned_to_input, account_key)
        if not assigned_user:
            return jsonify({'success': False, 'error': 'Assigned user does not exist'}), 404
        assigned_to = assigned_user['user_key']
        # Allow self-assignment for any user
        if assigned_to != user_key and 'admin' not in roles:
            return jsonify({'success': False, 'error': 'Only admin can assign tasks to other users'}), 403
        # Set default task_date as current date if not provided
        task_date = data.get('task_date')
        if not task_date:
            task_date = get_default_task_date()
        # Set default end_date as 24 hours from creation if not provided
        end_date = data.get('end_date')
        if not end_date:
            end_date = get_default_end_date()
        # Get user's timezone from settings, default to IST
        user_tz = 'Asia/Kolkata'
        if hasattr(assigned_user, 'settings') and assigned_user.settings.get('timezone'):
            user_tz = assigned_user.settings['timezone']
        tz = timezone(user_tz)
        # Convert end_date and task_date to user's timezone if possible
        try:
            # Try to parse and localize end_date
            dt_format = '%Y-%m-%d %H:%M'
            try:
                dt = datetime.strptime(end_date, dt_format)
            except Exception:
                dt_format = '%Y-%m-%d'
                dt = datetime.strptime(end_date, dt_format)
            dt = tz.localize(dt)
            end_date = dt.strftime(dt_format)
        except Exception:
            pass
        try:
            dt_format = '%Y-%m-%d %H:%M'
            try:
                dt = datetime.strptime(task_date, dt_format)
            except Exception:
                dt_format = '%Y-%m-%d'
                dt = datetime.strptime(task_date, dt_format)
            dt = tz.localize(dt)
            task_date = dt.strftime(dt_format)
        except Exception:
            pass
        # Default fields
        task_data = {
            'user_key': user_key,
            'reporter': user_key,
            'assignee': assigned_to,
            'assigned_to': assigned_to,
            'title': data.get('title'),
            'description': data.get('description', ''),
            'status': data.get('status', 'pending'),
            'end_date': end_date,
            'task_date': task_date,
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
        # Set high priority if due date is < 30min from now
        try:
            if end_date:
                # Parse end_date as 'YYYY-MM-DD HH:mm' or 'YYYY-MM-DD'
                try:
                    end_dt = time.strptime(end_date, '%Y-%m-%d %H:%M')
                except Exception:
                    end_dt = time.strptime(end_date, '%Y-%m-%d')
                end_epoch = int(time.mktime(end_dt))
                now_epoch = int(time.time())
                if 0 < end_epoch - now_epoch < 1800:
                    task_data['priority'] = 1
        except Exception:
            pass
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
            if 'task_id' not in t:
                t['task_id'] = t['_id']  # fallback for legacy tasks
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
            # Critical: priority == 1
            if t.get('priority') == 1:
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
        account_key = payload.get('account_key')
        roles = payload.get('roles', [])
        data = request.get_json(force=True)
        update_fields = dict(data)
        update_fields.pop('_id', None)  # Remove immutable _id field before update
        task = task_repository.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        new_assignee_input = update_fields.get('assignee') or update_fields.get('assigned_to')
        if new_assignee_input and new_assignee_input != task.get('assignee', task.get('assigned_to')):
            assigned_user = resolve_user(new_assignee_input, account_key)
            if not assigned_user:
                return jsonify({'success': False, 'error': 'Assigned user does not exist'}), 404
            new_assignee = assigned_user['user_key']
            # Allow self-assignment for any user
            if new_assignee != user_key:
                if 'admin' not in roles:
                    admin_user = mongo_db_repository.find_one('users', {'roles': {'$in': ['admin']}, 'account_key': account_key})
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
        if not updated:
            logging.error(f"Task update failed for task_id={task_id}, user_key={user_key}, update_fields={update_fields}")
            return jsonify({'success': False, 'error': 'Task update failed'}), 400
        logging.info(f"Task updated successfully for task_id={task_id}, user_key={user_key}")
        return jsonify({'success': True, 'updated': True}), 200
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
        account_key = payload.get('account_key')
        roles = payload.get('roles', [])
        data = request.get_json(force=True)
        new_assignee_input = data.get('new_assignee')
        if not new_assignee_input:
            return jsonify({'success': False, 'error': 'Missing new_assignee'}), 400
        task = task_repository.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Task not found'}), 404
        assigned_user = resolve_user(new_assignee_input, account_key)
        if not assigned_user:
            return jsonify({'success': False, 'error': 'New assignee does not exist'}), 404
        new_assignee = assigned_user['user_key']
        if 'admin' not in roles and user_key != task.get('assignee', task.get('assigned_to')):
            return jsonify({'success': False, 'error': 'Permission denied'}), 403
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
