from flask import Blueprint, request, current_app
from fin_server.repository.media.task_repository import TaskRepository
from fin_server.repository.mongo_helper import get_collection
# Initialize mongo manager first and provide its DB to repositories
from fin_server.security.authentication import UnauthorizedError
from fin_server.utils.generator import resolve_user, get_time_date
from fin_server.utils.helpers import get_request_payload, respond_error, respond_success

from pytz import timezone
import time
import logging
from datetime import datetime
from fin_server.dto.task_dto import TaskDTO


# Initialize mongo manager and repositories, then construct repo-backed TaskRepository

task_repo = get_collection('task')
user_repo = get_collection('users')

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
        # Accept both 'assignee' and 'assigned_to' for backward compatibility
        assignee_input = data.get('assignee') or data.get('assigned_to')
        # If assignee not provided, default to self-assignment
        if not assignee_input:
            assignee_input = user_key
        # Resolve assignee to user object
        if assignee_input == user_key:
            assigned_user = user_repo.find_one({'user_key': user_key, 'account_key': account_key})
        else:
            assigned_user = resolve_user(assignee_input, account_key)
        if not assigned_user:
            return respond_error('Assigned user does not exist', status=404)
        assignee = assigned_user['user_key']
        # Allow self-assignment for any user
        if assignee != user_key and 'admin' not in roles:
            return respond_error('Only admin can assign tasks to other users', status=403)
        # Set default task_date as current date if not provided (IST by default)
        task_date = data.get('task_date')
        if not task_date:
            task_date = get_time_date(include_time=False)
        # Set default end_date as current date+time if not provided (IST by default)
        end_date = data.get('end_date')
        if not end_date:
            end_date = get_time_date(include_time=True)
        # Get user's timezone from settings, default to IST (Asia/Kolkata)
        user_settings = assigned_user.get('settings') if isinstance(assigned_user, dict) else None
        user_tz = (user_settings or {}).get('timezone', 'Asia/Kolkata')
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
            'assignee': assignee,
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
        # Persist using TaskDTO.save for canonical behavior
        try:
            task_data['task_id'] = task_data.get('task_id') or None
            td = TaskDTO.from_request(task_data)
            res = td.save(repo=task_repo, collection_name='tasks', upsert=True)
            task_id = getattr(res, 'inserted_id', res)
            # Some repo.create implementations return inserted id or the doc
            if isinstance(task_id, dict):
                task_id = task_id.get('task_id') or task_id.get('_id')
        except Exception:
            task_id = task_repo.create(task_data)
        current_app.logger.info(f'Task created with id: {task_id}, account={account_key}, user={user_key}')
        # Build DTO for returned task
        try:
            task_data['task_id'] = task_id
            task_dto = TaskDTO.from_request(task_data)
            return respond_success(task_dto.to_dict(), status=201)
        except Exception:
            return respond_success({'task_id': task_id}, status=201)
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
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

        def _parse_to_epoch(s: str):
            if not s:
                return None
            # Try ISO first
            try:
                dt = datetime.fromisoformat(s)
                return int(dt.timestamp())
            except Exception:
                pass
            # Try common formats
            fmts = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']
            for f in fmts:
                try:
                    dt = datetime.strptime(s, f)
                    return int(time.mktime(dt.timetuple()))
                except Exception:
                    continue
            # Last resort: try to parse as float epoch
            try:
                return int(float(s))
            except Exception:
                return None

        for t in tasks:
            # Convert using DTO when possible
            try:
                td = TaskDTO.from_doc(t)
                tdict = td.to_dict()
            except Exception:
                t['_id'] = str(t['_id'])
                tdict = t
            status = str(tdict.get('status', '')).lower()
            if status == 'pending':
                meta['pending'] += 1
            elif status == 'inprogress' or status == 'in-progress':
                meta['inprogress'] += 1
            elif status == 'completed' or status == 'done':
                meta['completed'] += 1
            end_date = tdict.get('endTime') or tdict.get('end_date') or tdict.get('endTime')
            if status not in ('completed',) and end_date:
                try:
                    end_epoch = _parse_to_epoch(end_date)
                    if end_epoch is not None and end_epoch < now:
                        meta['overdue'] += 1
                except Exception:
                    pass
            if tdict.get('priority') in (1, '1', 'critical'):
                meta['critical'] += 1
            if tdict.get('viewed'):
                meta['read'] += 1
            else:
                meta['unread'] += 1
            task_objs.append(tdict)
        return respond_success({'meta': meta, 'tasks': task_objs})
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception as e:
        logging.exception("Error in get_tasks")
        return respond_error('Server error', status=500)

@task_bp.route('/<task_id>', methods=['GET'])
def get_task(task_id):
    """Get a single task by ID.

    Supports flexible lookup by:
      - task_id (business id used in most APIs)
      - Mongo _id string (id field returned by TaskDTO)
    """
    try:
        _ = get_request_payload(request)
        task = task_repo.find_by_any_id(task_id)
        if not task:
            return respond_error('Task not found', status=404)
        try:
            td = TaskDTO.from_doc(task)
            return respond_success(td.to_dict())
        except Exception:
            task['_id'] = str(task.get('_id'))
            task['id'] = task.get('task_id') or task['_id']
            return respond_success(task)
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        logging.exception('Error in get_task')
        return respond_error('Server error', status=500)

@task_bp.route('/<task_id>', methods=['PUT'])
def update_task(task_id):
    try:
        payload = get_request_payload(request)
        user_key = payload.get('user_key')
        account_key = payload.get('account_key')
        roles = payload.get('roles', [])
        data = request.get_json(force=True)
        current_app.logger.debug('PUT /task/%s called', task_id)
        # Normalize common camelCase fields coming from UI into backend field names
        if isinstance(data, dict):
            # id/taskId -> task_id (query still uses URL param task_id)
            if 'taskId' in data and 'task_id' not in data:
                data['task_id'] = data.get('taskId')
            # assignedTo -> assignee
            if 'assignedTo' in data and 'assignee' not in data:
                data['assignee'] = data.get('assignedTo')
            # scheduledDate -> task_date
            if 'scheduledDate' in data and 'task_date' not in data:
                data['task_date'] = data.get('scheduledDate')
            # endDate -> end_date
            if 'endDate' in data and 'end_date' not in data:
                data['end_date'] = data.get('endDate')
            # remindBefore -> remind_before
            if 'remindBefore' in data and 'remind_before' not in data:
                data['remind_before'] = data.get('remindBefore')
            # reminderTime -> reminder_time
            if 'reminderTime' in data and 'reminder_time' not in data:
                data['reminder_time'] = data.get('reminderTime')
            # userKey -> user_key
            if 'userKey' in data and 'user_key' not in data:
                data['user_key'] = data.get('userKey')
            # pondId -> pond_id
            if 'pondId' in data and 'pond_id' not in data:
                data['pond_id'] = data.get('pondId')
        update_fields = dict(data)
        update_fields.pop('_id', None)  # Remove immutable _id field before update
        # Flexible lookup by task_id or _id
        task = task_repo.find_by_any_id(task_id)
        if not task:
            current_app.logger.warning('PUT /task/%s: task not found', task_id)
            return respond_error('Task not found', status=404)
        current_app.logger.debug('PUT /task/%s existing task doc: %s', task_id, task)
        new_assignee_input = update_fields.get('assignee')
        if new_assignee_input and new_assignee_input != task.get('assignee'):
            assigned_user = resolve_user(new_assignee_input, account_key)
            if not assigned_user:
                return respond_error('Assigned user does not exist', status=404)
            new_assignee = assigned_user['user_key']
            # Allow self-assignment for any user
            if new_assignee != user_key:
                if 'admin' not in roles:
                    admin_user = user_repo.find_one({'roles': {'$in': ['admin']}, 'account_key': account_key})
                    if not admin_user or new_assignee != admin_user['user_key'] or task.get('assignee') != user_key:
                        return respond_error('Only admin can assign to other users, or user can reassign their own task to admin', status=403)
            history = task.get('history', [])
            history.append({
                'from': task.get('assignee'),
                'to': new_assignee,
                'by': user_key,
                'timestamp': int(time.time())
            })
            update_fields['history'] = history
            update_fields['assignee'] = new_assignee
        current_app.logger.debug('PUT /task/%s final update_fields: %s', task_id, update_fields)
        # Update by task_id and, as a fallback, by _id
        updated = task_repo.update({'task_id': task.get('task_id') or task_id}, update_fields)
        if not updated and task.get('_id'):
            updated = task_repo.update({'_id': task.get('_id')}, update_fields)
        # If nothing was modified but the task exists, treat it as a no-op success instead of failing
        if not updated:
            current_app.logger.info('PUT /task/%s: no fields modified (no-op update). Returning success.', task_id)
        else:
            current_app.logger.info('Task updated successfully for task_id=%s, user_key=%s', task.get('task_id') or task_id, user_key)
        # Return updated task via DTO
        try:
            refreshed = task_repo.find_by_any_id(task.get('task_id') or task_id)
            td = TaskDTO.from_doc(refreshed)
            return respond_success(td.to_dict())
        except Exception:
            return respond_success({'updated': bool(updated)})
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        logging.exception("Error in update_task")
        return respond_error('Server error', status=500)

@task_bp.route('/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    try:
        payload = get_request_payload(request)
        user_key = payload.get('user_key')
        # support deleting by task_id or _id
        task = task_repo.find_by_any_id(task_id)
        deleted = 0
        if task:
            if task.get('task_id'):
                deleted = task_repo.delete({'task_id': task.get('task_id')})
            if not deleted and task.get('_id'):
                deleted = task_repo.delete({'_id': task.get('_id')})
        return respond_success({'deleted': bool(deleted)})
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        logging.exception('Error in delete_task')
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
        task = task_repo.find_by_any_id(task_id)
        if not task:
            return respond_error('Task not found', status=404)
        assigned_user = resolve_user(new_assignee_input, account_key)
        if not assigned_user:
            return respond_error('New assignee does not exist', status=404)
        new_assignee = assigned_user['user_key']
        if 'admin' not in roles and user_key != task.get('assignee'):
            return respond_error('Permission denied', status=403)
        history = task.get('history', [])
        history.append({
            'from': task.get('assignee'),
            'to': new_assignee,
            'by': user_key,
            'timestamp': int(time.time())
        })
        update_fields = {
            'assignee': new_assignee,
            'history': history
        }
        updated = task_repo.update({'task_id': task.get('task_id') or task_id}, update_fields)
        if not updated and task.get('_id'):
            updated = task_repo.update({'_id': task.get('_id')}, update_fields)
        try:
            refreshed = task_repo.find_by_any_id(task.get('task_id') or task_id)
            td = TaskDTO.from_doc(refreshed)
            return respond_success(td.to_dict())
        except Exception:
            return respond_success({'updated': bool(updated)})
    except UnauthorizedError as ue:
        return respond_error(str(ue), status=401)
    except Exception:
        logging.exception('Error in move_task')
        return respond_error('Server error', status=500)

# Remove misplaced API routes under task_bp and provide proper api blueprint
from flask import Blueprint

task_api_bp = Blueprint('task_api', __name__, url_prefix='/api')

@task_api_bp.route('/schedules', methods=['GET'])
def api_list_schedules():
    try:
        payload = get_request_payload(request)
        query = {}
        pondId = request.args.get('pondId') or request.args.get('pond_id')
        if pondId:
            query['pond_id'] = pondId
        # Accept both assignedTo and assigned_to query params for backward compatibility
        assignee_filter = request.args.get('assignee') or request.args.get('assignedTo') or request.args.get('assigned_to')
        if assignee_filter:
            query['assignee'] = assignee_filter
        status = request.args.get('status')
        if status:
            query['status'] = status
        tasks = task_repo.find(query)
        out = []
        for t in tasks:
            try:
                td = TaskDTO.from_doc(t)
                out.append(td.to_dict())
            except Exception:
                t['_id'] = str(t.get('_id'))
                t['id'] = t.get('task_id') or t['_id']
                out.append(t)
        return respond_success({'data': out})
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception('Error in api_list_schedules')
        return respond_error('Server error', status=500)

@task_api_bp.route('/schedules', methods=['POST'])
def api_create_schedule():
    try:
        payload = get_request_payload(request)
        data = request.get_json(force=True)
        task_data = dict(data)
        if 'pondId' in data and 'pond_id' not in data:
            task_data['pond_id'] = data['pondId']
        task_data['user_key'] = payload.get('user_key')
        # Use repository create if available
        try:
            td = TaskDTO.from_request(task_data)
            res = td.save(repo=task_repo, collection_name='tasks', upsert=True)
            inserted = getattr(res, 'inserted_id', res)
            task_id = inserted if inserted else task_data.get('task_id')
            task_data['task_id'] = task_id
            return respond_success({'data': TaskDTO.from_request(task_data).to_dict()}, status=201)
        except Exception:
            try:
                res = task_repo.collection.insert_one(task_data)
                task_id = str(res.inserted_id)
                task_data['task_id'] = task_id
                td = TaskDTO.from_request(task_data)
                return respond_success({'data': td.to_dict()}, status=201)
            except Exception:
                return respond_error('Failed to create task', status=500)
    except UnauthorizedError as e:
        return respond_error(str(e), status=401)
    except Exception as e:
        current_app.logger.exception('Error in api_create_schedule')
        return respond_error('Server error', status=500)

@task_api_bp.route('/schedules/<sched_id>', methods=['PATCH'])
def api_update_schedule(sched_id):
    try:
        data = request.get_json(force=True)
        # Use the same flexible id resolution logic as other task routes
        task = task_repo.find_by_any_id(sched_id)
        if not task:
            return respond_error('Task not found', status=404)
        key = task.get('task_id') or task.get('_id')
        updated = task_repo.update({'task_id': key}, data)
        if not updated and task.get('_id'):
            updated = task_repo.update({'_id': task.get('_id')}, data)
        updated_task = task_repo.find_by_any_id(key)
        try:
            td = TaskDTO.from_doc(updated_task)
            return respond_success({'data': td.to_dict()})
        except Exception:
            return respond_success({'data': {'updated': True}})
    except Exception:
        current_app.logger.exception('Error in api_update_schedule')
        return respond_error('Server error', status=500)

@task_api_bp.route('/schedules/<sched_id>', methods=['DELETE'])
def api_delete_schedule(sched_id):
    try:
        task = task_repo.find_by_any_id(sched_id)
        deleted = 0
        if task:
            if task.get('task_id'):
                deleted = task_repo.delete({'task_id': task.get('task_id')})
            if not deleted and task.get('_id'):
                deleted = task_repo.delete({'_id': task.get('_id')})
        return respond_success({'data': {'deleted': bool(deleted)}})
    except Exception:
        current_app.logger.exception('Error in api_delete_schedule')
        return respond_error('Server error', status=500)
