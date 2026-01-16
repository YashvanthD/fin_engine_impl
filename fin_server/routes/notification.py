"""Notification and Alert routes with WebSocket integration.

This module provides REST API endpoints for notifications and alerts.
All create/update/delete operations also emit events via WebSocket.

Endpoints:
- /api/notification/* - Notification CRUD
- /api/notification/alert/* - Alert CRUD

WebSocket Events (emitted automatically):
- notification:new, notification:read, notification:count
- alert:new, alert:acknowledged, alert:count
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
from fin_server.websocket.handlers.notification_handler import NotificationHandler
from fin_server.websocket.handlers.alert_handler import AlertHandler

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
    normalized['id'] = normalized.get('notification_id') or str(normalized.get('_id', ''))
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
    """Create a notification and emit via WebSocket.

    Request Body:
        {
            "user_key": "target_user_key",  // Required
            "title": "Notification Title",   // Required
            "message": "Notification body",  // Required
            "type": "info|warning|error|success",
            "priority": "low|normal|high",
            "data": {},
            "link": "/path/to/resource"
        }

    WebSocket Event: notification:new (to target user)
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"POST /api/notification | account_key: {account_key}, user_key: {user_key}")

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

    # Create notification and emit via WebSocket
    notification_id = NotificationHandler.create_and_emit(
        account_key=account_key,
        target_user_key=target_user_key,
        title=title,
        message=message,
        notification_type=data.get('type', 'info'),
        priority=data.get('priority', 'normal'),
        data=data.get('data'),
        link=data.get('link'),
        created_by=user_key
    )

    if notification_id:
        return respond_success({
            'notification_id': notification_id,
            'message': 'Notification created and delivered via WebSocket'
        }, status=201)
    else:
        return respond_error('Failed to create notification', status=500)


@notification_bp.route('/', methods=['GET'])
@notification_bp.route('', methods=['GET'])
@handle_errors
@require_auth
def list_notifications(auth_payload):
    """List notifications for the current user.

    Query Params:
        unread: bool - Show only unread (default: false)
        limit: int - Max results (default: 50)
        skip: int - Offset for pagination
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"GET /api/notification | account_key: {account_key}, user_key: {user_key}")

    unread_only = request.args.get('unread', 'false').lower() == 'true'
    limit = min(int(request.args.get('limit', 50)), 100)
    skip = int(request.args.get('skip', 0))

    if not notification_repo:
        return respond_error('Notification service unavailable', status=503)

    try:
        query = {'account_key': account_key, 'user_key': user_key}
        if unread_only:
            query['read'] = False

        notifications = list(
            notification_repo.collection.find(query)
            .sort('created_at', -1)
            .skip(skip)
            .limit(limit)
        )

        result = [_normalize_notification(n) for n in notifications]

        # Get unread count
        unread_count = notification_repo.collection.count_documents({
            'account_key': account_key,
            'user_key': user_key,
            'read': False
        })

        return respond_success({
            'notifications': result,
            'count': len(result),
            'unread_count': unread_count,
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

    if not notification_repo:
        return respond_error('Notification service unavailable', status=503)

    try:
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
    """Mark a notification as read and emit via WebSocket.

    WebSocket Events: notification:read, notification:count
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"PUT /api/notification/{notification_id}/read | account_key: {account_key}, user_key: {user_key}")

    success = NotificationHandler.mark_read_and_emit(notification_id, user_key)

    if success:
        return respond_success({'message': 'Notification marked as read'})
    else:
        return respond_error('Notification not found', status=404)


@notification_bp.route('/read-all', methods=['PUT', 'POST'])
@handle_errors
@require_auth
def mark_all_notifications_read(auth_payload):
    """Mark all notifications as read and emit via WebSocket.

    WebSocket Events: notification:read_all, notification:count
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"PUT /api/notification/read-all | account_key: {account_key}, user_key: {user_key}")

    updated_count = NotificationHandler.mark_all_read_and_emit(user_key, account_key)

    return respond_success({
        'message': 'All notifications marked as read',
        'updated_count': updated_count
    })


@notification_bp.route('/<notification_id>', methods=['DELETE'])
@handle_errors
@require_auth
def delete_notification(notification_id, auth_payload):
    """Delete a notification and emit via WebSocket.

    WebSocket Event: notification:deleted
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"DELETE /api/notification/{notification_id} | account_key: {account_key}, user_key: {user_key}")

    success = NotificationHandler.delete_and_emit(notification_id, user_key)

    if success:
        return respond_success({'message': 'Notification deleted', 'notification_id': notification_id})
    else:
        return respond_error('Notification not found', status=404)


@notification_bp.route('/broadcast', methods=['POST'])
@handle_errors
@require_auth
@require_admin
def broadcast_notification(auth_payload):
    """Broadcast notification to all users in account (admin only).

    WebSocket Event: notification:new (to all users)
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

    count = NotificationHandler.broadcast_and_emit(
        account_key=account_key,
        title=title,
        message=message,
        notification_type=data.get('type', 'info'),
        priority=data.get('priority', 'normal'),
        data=data.get('data'),
        created_by=user_key
    )

    return respond_success({
        'message': 'Broadcast notification sent',
        'recipients_count': count
    }, status=201)


# =============================================================================
# Alert Endpoints (/api/notification/alert/*)
# =============================================================================

@notification_bp.route('/alert', methods=['POST'])
@notification_bp.route('/alert/', methods=['POST'])
@handle_errors
@require_auth
def create_alert(auth_payload):
    """Create an alert and emit via WebSocket to all account users.

    Request Body:
        {
            "title": "Alert Title",
            "message": "Alert description",
            "type": "info|warning|critical|success",
            "severity": "low|medium|high|critical",
            "source": "system|pond|task|expense",
            "source_id": "related_entity_id"
        }

    WebSocket Event: alert:new (to all account users)
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"POST /api/notification/alert | account_key: {account_key}, user_key: {user_key}")

    data = request.get_json(force=True)
    title = data.get('title')
    message = data.get('message')

    if not title:
        return respond_error('title is required', status=400)
    if not message:
        return respond_error('message is required', status=400)

    alert_id = AlertHandler.create_and_emit(
        account_key=account_key,
        title=title,
        message=message,
        alert_type=data.get('type', 'warning'),
        severity=data.get('severity', 'medium'),
        source=data.get('source', 'system'),
        source_id=data.get('source_id'),
        auto_dismiss=data.get('auto_dismiss', False),
        dismiss_after_minutes=data.get('dismiss_after_minutes'),
        created_by=user_key
    )

    if alert_id:
        return respond_success({
            'alert_id': alert_id,
            'message': 'Alert created and delivered via WebSocket'
        }, status=201)
    else:
        return respond_error('Failed to create alert', status=500)


@notification_bp.route('/alert', methods=['GET'])
@notification_bp.route('/alert/', methods=['GET'])
@handle_errors
@require_auth
def list_alerts(auth_payload):
    """List alerts for the account.

    Query Params:
        unacknowledged: bool - Show only unacknowledged
        severity: str - Filter by severity
        type: str - Filter by type
        limit: int - Max results
        skip: int - Offset
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"GET /api/notification/alert | account_key: {account_key}, user_key: {user_key}")

    unacknowledged_only = request.args.get('unacknowledged', 'false').lower() == 'true'
    severity = request.args.get('severity')
    alert_type = request.args.get('type')
    limit = min(int(request.args.get('limit', 50)), 100)
    skip = int(request.args.get('skip', 0))

    if not alerts_repo:
        return respond_error('Alert service unavailable', status=503)

    try:
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

        # Get unacknowledged count
        unack_count = alerts_repo.collection.count_documents({
            'account_key': account_key,
            'acknowledged': False
        })

        return respond_success({
            'alerts': result,
            'count': len(result),
            'unacknowledged_count': unack_count,
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

    if not alerts_repo:
        return respond_error('Alert service unavailable', status=503)

    try:
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
def acknowledge_alert_route(alert_id, auth_payload):
    """Acknowledge an alert and emit via WebSocket.

    WebSocket Events: alert:acknowledged, alert:count
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"PUT /api/notification/alert/{alert_id}/acknowledge | account_key: {account_key}, user_key: {user_key}")

    success = AlertHandler.acknowledge_and_emit(alert_id, account_key, user_key)

    if success:
        return respond_success({'message': 'Alert acknowledged', 'alert_id': alert_id})
    else:
        return respond_error('Alert not found', status=404)


@notification_bp.route('/alert/<alert_id>', methods=['DELETE'])
@handle_errors
@require_auth
@require_admin
def delete_alert_route(alert_id, auth_payload):
    """Delete an alert (admin only) and emit via WebSocket.

    WebSocket Event: alert:deleted
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"DELETE /api/notification/alert/{alert_id} | account_key: {account_key}, user_key: {user_key}")

    success = AlertHandler.delete_and_emit(alert_id, account_key)

    if success:
        return respond_success({'message': 'Alert deleted', 'alert_id': alert_id})
    else:
        return respond_error('Alert not found', status=404)


# =============================================================================
# WebSocket Info Endpoint
# =============================================================================

@notification_bp.route('/ws-info', methods=['GET'])
@handle_errors
@require_auth
def get_websocket_info(auth_payload):
    """Get WebSocket connection info and available events.

    Returns info about how to connect to WebSocket for real-time updates.
    """
    return respond_success({
        'websocket': {
            'url': '/socket.io',
            'auth': {
                'method': 'token',
                'header': 'Authorization: Bearer <token>',
                'query': '?token=<token>'
            },
            'events': {
                'notification': [
                    'notification:new',
                    'notification:read',
                    'notification:read_all',
                    'notification:deleted',
                    'notification:count'
                ],
                'alert': [
                    'alert:new',
                    'alert:acknowledged',
                    'alert:deleted',
                    'alert:count'
                ],
                'client_events': [
                    'notification:mark_read',
                    'notification:mark_all_read',
                    'alert:acknowledge'
                ]
            }
        },
        'note': 'Connect to WebSocket for real-time notifications instead of polling'
    })
