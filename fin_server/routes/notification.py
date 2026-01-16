"""Notification and Alert routes for creating and managing notifications.

This module provides endpoints for:
- Creating notifications/alerts
- Listing notifications for a user
- Marking notifications as read/delivered
- Deleting notifications

All endpoints are under /api/notification/*
"""
import logging
from datetime import datetime

from flask import Blueprint, request
from werkzeug.exceptions import Unauthorized

from fin_server.exception.UnauthorizedError import UnauthorizedError
from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.decorators import handle_errors, require_auth, require_admin
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc
from fin_server.utils.generator import generate_uuid_hex
from fin_server.utils.time_utils import get_time_date_dt

logger = logging.getLogger(__name__)

# Blueprint
notification_bp = Blueprint('notification', __name__, url_prefix='/api/notification')

# Repository
notification_repo = get_collection('notification')
alerts_repo = get_collection('alerts')


# =============================================================================
# Helper Functions
# =============================================================================

def _normalize_notification(doc):
    """Normalize notification document."""
    if not doc:
        return None
    normalized = normalize_doc(doc)
    normalized['id'] = str(normalized.get('_id', ''))
    return normalized


def _normalize_alert(doc):
    """Normalize alert document."""
    if not doc:
        return None
    normalized = normalize_doc(doc)
    normalized['id'] = normalized.get('alert_id') or str(normalized.get('_id', ''))
    return normalized


# =============================================================================
# Notification Endpoints (/api/notification/*)
# =============================================================================

@notification_bp.route('/', methods=['POST'])
@notification_bp.route('', methods=['POST'])
@handle_errors
@require_auth
def create_notification(auth_payload):
    """Create a new notification.

    Request Body:
        {
            "user_key": "target_user_key",  // Required - who receives the notification
            "title": "Notification Title",   // Required
            "message": "Notification body",  // Required
            "type": "info|warning|error|success",  // Optional, default: "info"
            "priority": "low|normal|high",   // Optional, default: "normal"
            "data": {},                      // Optional - additional data
            "link": "/path/to/resource"      // Optional - link to related resource
        }
    """
    requester_account_key = auth_payload.get('account_key')
    requester_user_key = auth_payload.get('user_key')
    logger.info(f"POST /api/notification | account_key: {requester_account_key}, user_key: {requester_user_key}")

    data = request.get_json(force=True)

    # Validate required fields
    target_user_key = data.get('user_key')
    title = data.get('title')
    message = data.get('message')

    if not target_user_key:
        return respond_error('user_key is required', status=400)
    if not title:
        return respond_error('title is required', status=400)
    if not message:
        return respond_error('message is required', status=400)

    # Build notification document
    notification_id = generate_uuid_hex(24)
    now = get_time_date_dt(include_time=True)

    notification_doc = {
        '_id': notification_id,
        'notification_id': notification_id,
        'account_key': requester_account_key,
        'user_key': target_user_key,
        'title': title,
        'message': message,
        'type': data.get('type', 'info'),
        'priority': data.get('priority', 'normal'),
        'data': data.get('data', {}),
        'link': data.get('link'),
        'read': False,
        'delivered': False,
        'created_by': requester_user_key,
        'created_at': now,
        'updated_at': now
    }

    try:
        if notification_repo:
            notification_repo.create(notification_doc)
        else:
            return respond_error('Notification service unavailable', status=503)

        logger.info(f"Notification created: {notification_id} for user: {target_user_key}")
        return respond_success({
            'notification_id': notification_id,
            'message': 'Notification created successfully'
        }, status=201)
    except Exception as e:
        logger.exception(f'Error creating notification: {e}')
        return respond_error('Failed to create notification', status=500)


@notification_bp.route('/', methods=['GET'])
@notification_bp.route('', methods=['GET'])
@handle_errors
@require_auth
def list_notifications(auth_payload):
    """List notifications for the current user."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"GET /api/notification | account_key: {account_key}, user_key: {user_key}")

    # Query params
    unread_only = request.args.get('unread', 'false').lower() == 'true'
    limit = int(request.args.get('limit', 50))
    skip = int(request.args.get('skip', 0))

    try:
        if not notification_repo:
            return respond_error('Notification service unavailable', status=503)

        query = {
            'account_key': account_key,
            'user_key': user_key
        }
        if unread_only:
            query['read'] = False

        notifications = list(
            notification_repo.collection.find(query)
            .sort('created_at', -1)
            .skip(skip)
            .limit(limit)
        )

        result = [_normalize_notification(n) for n in notifications]
        return respond_success({
            'notifications': result,
            'count': len(result),
            'meta': {'limit': limit, 'skip': skip}
        })
    except Exception as e:
        logger.exception(f'Error listing notifications: {e}')
        return respond_error('Failed to list notifications', status=500)


@notification_bp.route('/<notification_id>', methods=['GET'])
@handle_errors
@require_auth
def get_notification(notification_id, auth_payload):
    """Get a specific notification."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"GET /api/notification/{notification_id} | account_key: {account_key}, user_key: {user_key}")

    try:
        if not notification_repo:
            return respond_error('Notification service unavailable', status=503)

        notification = notification_repo.find_one({
            'notification_id': notification_id,
            'account_key': account_key,
            'user_key': user_key
        })

        if not notification:
            return respond_error('Notification not found', status=404)

        return respond_success({'notification': _normalize_notification(notification)})
    except Exception as e:
        logger.exception(f'Error getting notification: {e}')
        return respond_error('Failed to get notification', status=500)


@notification_bp.route('/<notification_id>/read', methods=['PUT', 'POST'])
@handle_errors
@require_auth
def mark_notification_read(notification_id, auth_payload):
    """Mark a notification as read."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"PUT /api/notification/{notification_id}/read | account_key: {account_key}, user_key: {user_key}")

    try:
        if not notification_repo:
            return respond_error('Notification service unavailable', status=503)

        result = notification_repo.update(
            {
                'notification_id': notification_id,
                'account_key': account_key,
                'user_key': user_key
            },
            {
                'read': True,
                'read_at': get_time_date_dt(include_time=True),
                'updated_at': get_time_date_dt(include_time=True)
            }
        )

        if result.modified_count == 0:
            return respond_error('Notification not found', status=404)

        return respond_success({'message': 'Notification marked as read'})
    except Exception as e:
        logger.exception(f'Error marking notification as read: {e}')
        return respond_error('Failed to update notification', status=500)


@notification_bp.route('/read-all', methods=['PUT', 'POST'])
@handle_errors
@require_auth
def mark_all_notifications_read(auth_payload):
    """Mark all notifications as read for the current user."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"PUT /api/notification/read-all | account_key: {account_key}, user_key: {user_key}")

    try:
        if not notification_repo:
            return respond_error('Notification service unavailable', status=503)

        result = notification_repo.update(
            {
                'account_key': account_key,
                'user_key': user_key,
                'read': False
            },
            {
                'read': True,
                'read_at': get_time_date_dt(include_time=True),
                'updated_at': get_time_date_dt(include_time=True)
            },
            multi=True
        )

        return respond_success({
            'message': 'All notifications marked as read',
            'updated_count': result.modified_count
        })
    except Exception as e:
        logger.exception(f'Error marking all notifications as read: {e}')
        return respond_error('Failed to update notifications', status=500)


@notification_bp.route('/<notification_id>', methods=['DELETE'])
@handle_errors
@require_auth
def delete_notification(notification_id, auth_payload):
    """Delete a notification."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"DELETE /api/notification/{notification_id} | account_key: {account_key}, user_key: {user_key}")

    try:
        if not notification_repo:
            return respond_error('Notification service unavailable', status=503)

        result = notification_repo.delete({
            'notification_id': notification_id,
            'account_key': account_key,
            'user_key': user_key
        })

        if result.deleted_count == 0:
            return respond_error('Notification not found', status=404)

        return respond_success({'message': 'Notification deleted', 'notification_id': notification_id})
    except Exception as e:
        logger.exception(f'Error deleting notification: {e}')
        return respond_error('Failed to delete notification', status=500)


# =============================================================================
# Alert Endpoints (/api/notification/alert/*)
# =============================================================================

@notification_bp.route('/alert', methods=['POST'])
@notification_bp.route('/alert/', methods=['POST'])
@handle_errors
@require_auth
def create_alert(auth_payload):
    """Create a new alert.

    Request Body:
        {
            "title": "Alert Title",           // Required
            "message": "Alert description",   // Required
            "type": "info|warning|critical|success",  // Optional, default: "warning"
            "severity": "low|medium|high|critical",   // Optional, default: "medium"
            "source": "system|pond|task|expense",     // Optional, default: "system"
            "source_id": "related_entity_id",         // Optional
            "auto_dismiss": true,             // Optional, default: false
            "dismiss_after_minutes": 60       // Optional, only if auto_dismiss is true
        }
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"POST /api/notification/alert | account_key: {account_key}, user_key: {user_key}")

    data = request.get_json(force=True)

    # Validate required fields
    title = data.get('title')
    message = data.get('message')

    if not title:
        return respond_error('title is required', status=400)
    if not message:
        return respond_error('message is required', status=400)

    # Build alert document
    alert_id = generate_uuid_hex(24)
    now = get_time_date_dt(include_time=True)

    alert_doc = {
        '_id': alert_id,
        'alert_id': alert_id,
        'account_key': account_key,
        'title': title,
        'message': message,
        'type': data.get('type', 'warning'),
        'severity': data.get('severity', 'medium'),
        'source': data.get('source', 'system'),
        'source_id': data.get('source_id'),
        'acknowledged': False,
        'acknowledged_by': None,
        'acknowledged_at': None,
        'auto_dismiss': data.get('auto_dismiss', False),
        'dismiss_after_minutes': data.get('dismiss_after_minutes'),
        'created_by': user_key,
        'created_at': now,
        'updated_at': now
    }

    try:
        if alerts_repo:
            alerts_repo.create(alert_doc)
        else:
            return respond_error('Alert service unavailable', status=503)

        logger.info(f"Alert created: {alert_id}")
        return respond_success({
            'alert_id': alert_id,
            'message': 'Alert created successfully'
        }, status=201)
    except Exception as e:
        logger.exception(f'Error creating alert: {e}')
        return respond_error('Failed to create alert', status=500)


@notification_bp.route('/alert', methods=['GET'])
@notification_bp.route('/alert/', methods=['GET'])
@handle_errors
@require_auth
def list_alerts(auth_payload):
    """List alerts for the account."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"GET /api/notification/alert | account_key: {account_key}, user_key: {user_key}")

    # Query params
    unacknowledged_only = request.args.get('unacknowledged', 'false').lower() == 'true'
    severity = request.args.get('severity')
    alert_type = request.args.get('type')
    limit = int(request.args.get('limit', 50))
    skip = int(request.args.get('skip', 0))

    try:
        if not alerts_repo:
            return respond_error('Alert service unavailable', status=503)

        query = {'account_key': account_key}
        if unacknowledged_only:
            query['acknowledged'] = False
        if severity:
            query['severity'] = severity
        if alert_type:
            query['type'] = alert_type

        alerts = list(
            alerts_repo.collection.find(query)
            .sort('created_at', -1)
            .skip(skip)
            .limit(limit)
        )

        result = [_normalize_alert(a) for a in alerts]
        return respond_success({
            'alerts': result,
            'count': len(result),
            'meta': {'limit': limit, 'skip': skip}
        })
    except Exception as e:
        logger.exception(f'Error listing alerts: {e}')
        return respond_error('Failed to list alerts', status=500)


@notification_bp.route('/alert/<alert_id>', methods=['GET'])
@handle_errors
@require_auth
def get_alert(alert_id, auth_payload):
    """Get a specific alert."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"GET /api/notification/alert/{alert_id} | account_key: {account_key}, user_key: {user_key}")

    try:
        if not alerts_repo:
            return respond_error('Alert service unavailable', status=503)

        alert = alerts_repo.find_one({
            'alert_id': alert_id,
            'account_key': account_key
        })

        if not alert:
            return respond_error('Alert not found', status=404)

        return respond_success({'alert': _normalize_alert(alert)})
    except Exception as e:
        logger.exception(f'Error getting alert: {e}')
        return respond_error('Failed to get alert', status=500)


@notification_bp.route('/alert/<alert_id>/acknowledge', methods=['PUT', 'POST'])
@handle_errors
@require_auth
def acknowledge_alert(alert_id, auth_payload):
    """Acknowledge an alert."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"PUT /api/notification/alert/{alert_id}/acknowledge | account_key: {account_key}, user_key: {user_key}")

    try:
        if not alerts_repo:
            return respond_error('Alert service unavailable', status=503)

        result = alerts_repo.update(
            {
                'alert_id': alert_id,
                'account_key': account_key
            },
            {
                'acknowledged': True,
                'acknowledged_by': user_key,
                'acknowledged_at': get_time_date_dt(include_time=True),
                'updated_at': get_time_date_dt(include_time=True)
            }
        )

        if result.modified_count == 0:
            return respond_error('Alert not found', status=404)

        return respond_success({'message': 'Alert acknowledged', 'alert_id': alert_id})
    except Exception as e:
        logger.exception(f'Error acknowledging alert: {e}')
        return respond_error('Failed to acknowledge alert', status=500)


@notification_bp.route('/alert/<alert_id>', methods=['DELETE'])
@handle_errors
@require_auth
@require_admin
def delete_alert(alert_id, auth_payload):
    """Delete an alert (admin only)."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"DELETE /api/notification/alert/{alert_id} | account_key: {account_key}, user_key: {user_key}")

    try:
        if not alerts_repo:
            return respond_error('Alert service unavailable', status=503)

        result = alerts_repo.delete({
            'alert_id': alert_id,
            'account_key': account_key
        })

        if result.deleted_count == 0:
            return respond_error('Alert not found', status=404)

        return respond_success({'message': 'Alert deleted', 'alert_id': alert_id})
    except Exception as e:
        logger.exception(f'Error deleting alert: {e}')
        return respond_error('Failed to delete alert', status=500)


# =============================================================================
# Broadcast Notification (Admin Only)
# =============================================================================

@notification_bp.route('/broadcast', methods=['POST'])
@handle_errors
@require_auth
@require_admin
def broadcast_notification(auth_payload):
    """Broadcast a notification to all users in the account (admin only).

    Request Body:
        {
            "title": "Notification Title",
            "message": "Notification body",
            "type": "info|warning|error|success",
            "priority": "low|normal|high"
        }
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"POST /api/notification/broadcast | account_key: {account_key}, user_key: {user_key}")

    data = request.get_json(force=True)

    title = data.get('title')
    message = data.get('message')

    if not title:
        return respond_error('title is required', status=400)
    if not message:
        return respond_error('message is required', status=400)

    try:
        # Get all users in the account
        user_repo = get_collection('users')
        if not user_repo:
            return respond_error('User service unavailable', status=503)

        users = list(user_repo.find({'account_key': account_key}))

        if not users:
            return respond_error('No users found in account', status=404)

        if not notification_repo:
            return respond_error('Notification service unavailable', status=503)

        now = get_time_date_dt(include_time=True)
        notifications_created = 0

        for user in users:
            target_user_key = user.get('user_key')
            if not target_user_key:
                continue

            notification_id = generate_uuid_hex(24)
            notification_doc = {
                '_id': notification_id,
                'notification_id': notification_id,
                'account_key': account_key,
                'user_key': target_user_key,
                'title': title,
                'message': message,
                'type': data.get('type', 'info'),
                'priority': data.get('priority', 'normal'),
                'data': data.get('data', {}),
                'broadcast': True,
                'read': False,
                'delivered': False,
                'created_by': user_key,
                'created_at': now,
                'updated_at': now
            }
            notification_repo.create(notification_doc)
            notifications_created += 1

        logger.info(f"Broadcast notification sent to {notifications_created} users")
        return respond_success({
            'message': 'Broadcast notification sent',
            'recipients_count': notifications_created
        }, status=201)
    except Exception as e:
        logger.exception(f'Error broadcasting notification: {e}')
        return respond_error('Failed to broadcast notification', status=500)

