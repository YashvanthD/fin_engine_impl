from flask import Blueprint, request, current_app
from fin_server.repository.task_repository import TaskRepository
from fin_server.repository.mongo_helper import MongoRepositorySingleton
from fin_server.security.authentication import UnauthorizedError
from fin_server.utils.generator import resolve_user, get_default_task_date, get_default_end_date
from fin_server.utils.helpers import get_request_payload, respond_error, respond_success
from pytz import timezone
import time
import logging
from datetime import datetime

task_repo = TaskRepository()
repo = MongoRepositorySingleton.get_instance()
user_repo = repo.user

task_bp = Blueprint('task', __name__, url_prefix='/task')

@task_bp.route('/', methods=['POST'])
def create_task():
    try:
        payload = get_request_payload(request)
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
            assigned_user = user_repo.find_one('users', {'user_key': user_key, 'account_key': account_key})
        else:
            assigned_user = resolve_user(assigned_to_input, account_key)
        if not assigned_user:
            return respond_error('Assigned user does not exist', status=404)
        assigned_to = assigned_user['user_key']
        # Allow self-assignment for any user
        if assigned_to != user_key and 'admin' not in roles:
            return respond_error('Only admin can assign tasks to other users', status=403)
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
        task_id = task_repo.create_task(task_data)
        current_app.logger.info(f'Task created with id: {task_id}, account={account_key}, user={user_key}')
        return respond_success({'task_id': task_id}, status=201)
    except Exception as e:
        logging.exception("Error in create_task")
        return respond_error('Server error', status=500)

@task_bp.route('/', methods=['GET'])
def get_tasks():
    current_app.logger.debug('GET /task/ called with args: %s', request.args)
    try:
        payload = get_request_payload(request)
        user_key = payload.get('user_key')
        query = request.args.to_dict()
        query['user_key'] = user_key
        tasks = task_repo.find(query)
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
            if 'viewed' not in t:
                t['viewed'] = False
            status = t.get('status', '').lower()
            if status == 'pending':
                meta['pending'] += 1
            elif status == 'inprogress':
                meta['inprogress'] += 1
            elif status == 'completed':
                meta['completed'] += 1
            end_date = t.get('end_date')
            if status != 'completed' and end_date:
                try:
                    end_epoch = int(time.mktime(time.strptime(end_date, '%Y-%m-%d')))
                    if end_epoch < now:
                        meta['overdue'] += 1
                except Exception:
                    pass
            if t.get('priority') == 1:
                meta['critical'] += 1
            if t['viewed']:
                meta['read'] += 1
            else:
                meta['unread'] += 1
            task_objs.append(t)
        return respond_success({'meta': meta, 'tasks': task_objs})
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        logging.exception("Error in get_tasks")
        return respond_error('Server error', status=500)

@task_bp.route('/<task_id>', methods=['PUT'])
def update_task(task_id):
    try:
        payload = get_request_payload(request)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        roles = payload.get('roles', [])
        data = request.get_json(force=True)
        update_fields = dict(data)
        update_fields.pop('_id', None)  # Remove immutable _id field before update
        task = task_repo.get_task(task_id)
        if not task:
            return respond_error('Task not found', status=404)
        new_assignee_input = update_fields.get('assignee') or update_fields.get('assigned_to')
        if new_assignee_input and new_assignee_input != task.get('assignee', task.get('assigned_to')):
            assigned_user = resolve_user(new_assignee_input, account_key)
            if not assigned_user:
                return respond_error('Assigned user does not exist', status=404)
            new_assignee = assigned_user['user_key']
            # Allow self-assignment for any user
            if new_assignee != user_key:
                if 'admin' not in roles:
                    admin_user = user_repo.find_one('users', {'roles': {'$in': ['admin']}, 'account_key': account_key})
                    if not admin_user or new_assignee != admin_user['user_key'] or task.get('assignee', task.get('assigned_to')) != user_key:
                        return respond_error('Only admin can assign to other users, or user can reassign their own task to admin', status=403)
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
        updated = task_repo.update_task(task_id, update_fields)
        if not updated:
            logging.error(f"Task update failed for task_id={task_id}, user_key={user_key}, update_fields={update_fields}")
            return respond_error('Task update failed', status=400)
        logging.info(f"Task updated successfully for task_id={task_id}, user_key={user_key}")
        return respond_success({'updated': True})
    except Exception as e:
        logging.exception("Error in update_task")
        return respond_error('Server error', status=500)

@task_bp.route('/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    try:
        payload = get_request_payload(request)
        user_key = payload.get('user_key')
        deleted = task_repo.delete(task_id)
        return respond_success({'deleted': bool(deleted)})
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        logging.exception("Error in delete_task")
        return respond_error('Server error', status=500)

@task_bp.route('/<task_id>/move', methods=['POST'])
def move_task(task_id):
    try:
        payload = get_request_payload(request)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        roles = payload.get('roles', [])
        data = request.get_json(force=True)
        new_assignee_input = data.get('new_assignee')
        if not new_assignee_input:
            return respond_error('Missing new_assignee', status=400)
        task = task_repo.get_task(task_id)
        if not task:
            return respond_error('Task not found', status=404)
        assigned_user = resolve_user(new_assignee_input, account_key)
        if not assigned_user:
            return respond_error('New assignee does not exist', status=404)
        new_assignee = assigned_user['user_key']
        if 'admin' not in roles and user_key != task.get('assignee', task.get('assigned_to')):
            return respond_error('Permission denied', status=403)
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
        updated = task_repo.update_task(task_id, update_fields)
        return respond_success({'updated': bool(updated)})
    except Exception as e:
        logging.exception("Error in move_task")
        return respond_error('Server error', status=500)
