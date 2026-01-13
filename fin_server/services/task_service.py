"""Task service - business logic for task/schedule management.

This module provides reusable functions for:
- Task creation and validation
- Task status and metadata calculations
- Assignment and reassignment logic
"""
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from fin_server.dto.task_dto import TaskDTO
from fin_server.utils.generator import resolve_user, get_time_date

logger = logging.getLogger(__name__)


# =============================================================================
# Date/Time Utilities
# =============================================================================

def parse_to_epoch(date_str: str) -> Optional[int]:
    """Parse a date string to epoch timestamp.

    Supports:
    - ISO format (datetime.fromisoformat)
    - Common formats: YYYY-MM-DD HH:MM:SS, YYYY-MM-DD HH:MM, YYYY-MM-DD
    - Numeric epoch string
    """
    if not date_str:
        return None

    # Try ISO format first
    try:
        dt = datetime.fromisoformat(str(date_str))
        return int(dt.timestamp())
    except (ValueError, TypeError):
        pass

    # Try common formats
    formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']
    for fmt in formats:
        try:
            dt = datetime.strptime(str(date_str), fmt)
            return int(time.mktime(dt.timetuple()))
        except (ValueError, TypeError):
            continue

    # Try parsing as numeric epoch
    try:
        return int(float(date_str))
    except (ValueError, TypeError):
        return None


# =============================================================================
# Task Metadata Calculation
# =============================================================================

def calculate_task_metadata(tasks: List[Dict]) -> Dict[str, int]:
    """Calculate aggregated metadata for a list of tasks.

    Returns counts for:
    - pending, inprogress, completed, overdue, critical, read, unread
    """
    now = int(time.time())
    meta = {
        'pending': 0,
        'inprogress': 0,
        'completed': 0,
        'overdue': 0,
        'critical': 0,
        'read': 0,
        'unread': 0
    }

    for task in tasks:
        status = str(task.get('status', '')).lower()

        if status == 'pending':
            meta['pending'] += 1
        elif status in ('inprogress', 'in-progress'):
            meta['inprogress'] += 1
        elif status in ('completed', 'done'):
            meta['completed'] += 1

        # Check for overdue
        end_date = task.get('endTime') or task.get('end_date')
        if status not in ('completed', 'done') and end_date:
            end_epoch = parse_to_epoch(end_date)
            if end_epoch is not None and end_epoch < now:
                meta['overdue'] += 1

        # Critical priority
        if task.get('priority') in (1, '1', 'critical'):
            meta['critical'] += 1

        # Read/unread
        if task.get('viewed'):
            meta['read'] += 1
        else:
            meta['unread'] += 1

    return meta


# =============================================================================
# Task Normalization
# =============================================================================

def normalize_task_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize camelCase fields to snake_case for backend storage.

    Handles common field name mappings from frontend to backend.
    """
    if not isinstance(data, dict):
        return data

    mappings = {
        'taskId': 'task_id',
        'assignedTo': 'assignee',
        'scheduledDate': 'task_date',
        'endDate': 'end_date',
        'remindBefore': 'remind_before',
        'reminderTime': 'reminder_time',
        'userKey': 'user_key',
        'pondId': 'pond_id',
    }

    result = dict(data)
    for camel, snake in mappings.items():
        if camel in result and snake not in result:
            result[snake] = result[camel]

    return result


def task_to_dto_dict(task: Dict) -> Dict[str, Any]:
    """Convert a task document to DTO dict format."""
    try:
        dto = TaskDTO.from_doc(task)
        return dto.to_dict()
    except Exception:
        # Fallback to basic normalization
        result = dict(task)
        result['_id'] = str(result.get('_id'))
        result['id'] = result.get('task_id') or result['_id']
        return result


# =============================================================================
# Assignment Logic
# =============================================================================

def validate_assignment(
    new_assignee_key: str,
    current_user_key: str,
    current_assignee_key: Optional[str],
    user_roles: List[str],
    account_key: str,
    user_repo
) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """Validate task assignment permissions.

    Args:
        new_assignee_key: User key of the new assignee
        current_user_key: User key of the user making the change
        current_assignee_key: Current task assignee (if any)
        user_roles: Roles of the current user
        account_key: Account key for user resolution
        user_repo: User repository for lookups

    Returns:
        Tuple of (is_valid, error_message, assigned_user_doc)
    """
    # Resolve the new assignee
    assigned_user = resolve_user(new_assignee_key, account_key)
    if not assigned_user:
        return False, 'Assigned user does not exist', None

    resolved_key = assigned_user['user_key']

    # Self-assignment is always allowed
    if resolved_key == current_user_key:
        return True, None, assigned_user

    # Admin can assign to anyone
    if 'admin' in user_roles:
        return True, None, assigned_user

    # Non-admin reassigning their own task to admin
    admin_user = user_repo.find_one({
        'roles': {'$in': ['admin']},
        'account_key': account_key
    })
    if admin_user and resolved_key == admin_user['user_key'] and current_assignee_key == current_user_key:
        return True, None, assigned_user

    return False, 'Only admin can assign tasks to other users', None


def create_assignment_history_entry(
    from_key: Optional[str],
    to_key: str,
    by_key: str
) -> Dict[str, Any]:
    """Create a history entry for task assignment change."""
    return {
        'from': from_key,
        'to': to_key,
        'by': by_key,
        'timestamp': int(time.time())
    }


# =============================================================================
# Task Priority Logic
# =============================================================================

def should_set_high_priority(end_date: str, threshold_minutes: int = 30) -> bool:
    """Check if task should be set to high priority based on due date.

    Returns True if end_date is within threshold_minutes from now.
    """
    if not end_date:
        return False

    end_epoch = parse_to_epoch(end_date)
    if end_epoch is None:
        return False

    now_epoch = int(time.time())
    time_until_due = end_epoch - now_epoch

    return 0 < time_until_due < (threshold_minutes * 60)


# =============================================================================
# Task Creation Helpers
# =============================================================================

def build_task_data(
    data: Dict[str, Any],
    user_key: str,
    assigned_to: str,
    user_timezone: str = 'Asia/Kolkata'
) -> Dict[str, Any]:
    """Build complete task data for creation.

    Sets defaults and normalizes fields.
    """
    from pytz import timezone

    remind_before = data.get('remind_before', 30)

    # Default dates
    task_date = data.get('task_date') or get_time_date(include_time=False)
    end_date = data.get('end_date') or get_time_date(include_time=True)

    # Localize dates to user timezone
    tz = timezone(user_timezone)
    for date_val in [task_date, end_date]:
        try:
            dt_format = '%Y-%m-%d %H:%M' if ' ' in str(date_val) else '%Y-%m-%d'
            dt = datetime.strptime(str(date_val), dt_format)
            dt = tz.localize(dt)
        except Exception:
            pass

    task_data = {
        'user_key': user_key,
        'reporter': user_key,
        'assignee': assigned_to,
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

    # Merge extra fields
    for k, v in data.items():
        if k not in task_data:
            task_data[k] = v

    # Auto-set high priority if due soon
    if should_set_high_priority(end_date):
        task_data['priority'] = 1

    return task_data

