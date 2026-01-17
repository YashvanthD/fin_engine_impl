"""Centralized WebSocket Hub.

Integrates Socket.IO with notification, alert, and chat events.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from flask import Flask
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect

from fin_server.websocket.event_emitter import (
    EventEmitter, set_socketio, set_user_tracking
)
from fin_server.repository.mongo_helper import get_collection
from fin_server.security.authentication import AuthSecurity

logger = logging.getLogger(__name__)


class WebSocketHub:
    """Centralized WebSocket Hub for real-time communication."""

    def __init__(self, socketio: SocketIO = None):
        self.socketio = socketio
        self.connected_users: Dict[str, Dict[str, Any]] = {}
        self.user_sockets: Dict[str, list] = {}
        self._initialized = False
        self._chat_handler = None

    def init_app(self, app: Flask, socketio: SocketIO):
        """Initialize the WebSocket hub."""
        logger.debug(f"WS_HUB: init app={app.name}, mode={getattr(socketio, 'async_mode', '?')}")

        self.socketio = socketio
        self.app = app

        set_socketio(socketio)
        set_user_tracking(self.connected_users, self.user_sockets)

        self._register_handlers()
        self._init_chat_handler()

        self._initialized = True
        logger.debug("WS_HUB: initialized")

    def _init_chat_handler(self):
        """Initialize chat handler."""
        try:
            from fin_server.websocket.handlers.chat_handler import init_chat_handler
            self._chat_handler = init_chat_handler(
                self.socketio,
                self.connected_users,
                self.user_sockets
            )
        except Exception as e:
            logger.error(f"WS_HUB: chat_handler init failed: {e}")

    def _register_handlers(self):
        """Register WebSocket event handlers."""

        @self.socketio.on_error_default
        def default_error_handler(e):
            logger.error(f"WS error: {e}")

        # =====================================================================
        # Connection Events
        # =====================================================================

        @self.socketio.on('connect')
        def handle_connect(auth=None):
            """Handle new WebSocket connection."""
            from flask import request

            socket_id = getattr(request, 'sid', None)
            logger.debug(f"WS connect: sid={socket_id}, ip={request.remote_addr}")

            # Get token from auth data or headers
            token = None
            if auth and isinstance(auth, dict):
                token = auth.get('token')

            if not token:
                token = request.headers.get('Authorization', '').replace('Bearer ', '')

            if not token:
                token = request.args.get('token', '')

            # Authenticate
            payload = self._authenticate(token)
            if not payload:
                logger.warning(f"WS auth failed: sid={socket_id}")
                emit('error', {'code': 'UNAUTHORIZED', 'message': 'Invalid token'})
                disconnect()
                return False

            user_key = payload.get('user_key')
            account_key = payload.get('account_key')

            logger.info(f"WS connected: user={user_key[:8]}..., sid={socket_id}")

            # Store connection
            self.connected_users[socket_id] = {
                'user_key': user_key,
                'account_key': account_key,
                'connected_at': datetime.utcnow().isoformat()
            }

            # Track user's sockets
            if user_key not in self.user_sockets:
                self.user_sockets[user_key] = []
            self.user_sockets[user_key].append(socket_id)

            # Join rooms
            join_room(user_key)
            join_room(account_key)

            # Send connection success
            emit('connected', {
                'message': 'Connected',
                'user_key': user_key,
                'socket_id': socket_id
            })

            # Notify presence
            EventEmitter.notify_presence(user_key, 'online', account_key)

            # Initialize chat
            if self._chat_handler:
                self._chat_handler.on_user_connected(user_key, account_key, socket_id)

            # Send pending events
            self._send_pending_events(user_key, account_key)

            return True

        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle WebSocket disconnection."""
            from flask import request

            socket_id = request.sid
            user_info = self.connected_users.pop(socket_id, None)

            if user_info:
                user_key = user_info.get('user_key')
                account_key = user_info.get('account_key')

                if user_key in self.user_sockets:
                    self.user_sockets[user_key] = [
                        s for s in self.user_sockets[user_key] if s != socket_id
                    ]

                    if not self.user_sockets[user_key]:
                        del self.user_sockets[user_key]
                        logger.debug(f"WS offline: user={user_key[:8]}...")
                        EventEmitter.notify_presence(user_key, 'offline', account_key)

                        if self._chat_handler:
                            self._chat_handler.on_user_disconnected(user_key, account_key)

        # =====================================================================
        # Notification Events
        # =====================================================================

        @self.socketio.on('notification:mark_read')
        def handle_notification_mark_read(data):
            """Mark notification as read."""
            user_info = self._get_user_from_socket()
            if not user_info:
                emit('error', {'code': 'UNAUTHORIZED'})
                return

            notification_id = data.get('notification_id')
            if not notification_id:
                emit('error', {'code': 'INVALID_DATA', 'message': 'notification_id required'})
                return

            notification_repo = get_collection('notification')
            if notification_repo is not None:
                notification_repo.update(
                    {'notification_id': notification_id, 'user_key': user_info['user_key']},
                    {'read': True, 'read_at': datetime.utcnow()}
                )

            EventEmitter.emit_to_user(
                user_info['user_key'],
                EventEmitter.NOTIFICATION_READ,
                {'notification_id': notification_id}
            )

        @self.socketio.on('notification:mark_all_read')
        def handle_notification_mark_all_read(data=None):
            """Mark all notifications as read."""
            user_info = self._get_user_from_socket()
            if not user_info:
                emit('error', {'code': 'UNAUTHORIZED'})
                return

            notification_repo = get_collection('notification')
            if notification_repo is not None:
                notification_repo.update(
                    {'user_key': user_info['user_key'], 'read': False},
                    {'read': True, 'read_at': datetime.utcnow()},
                    multi=True
                )

            EventEmitter.emit_to_user(
                user_info['user_key'],
                EventEmitter.NOTIFICATION_READ_ALL,
                {}
            )
            EventEmitter.update_notification_count(user_info['user_key'], 0)

        # =====================================================================
        # Alert Events
        # =====================================================================

        @self.socketio.on('alert:acknowledge')
        def handle_alert_acknowledge(data):
            """Acknowledge an alert."""
            from flask import request
            socket_id = request.sid

            user_info = self._get_user_from_socket()
            if not user_info:
                emit('alert:error', {'code': 'UNAUTHORIZED'})
                return {'success': False, 'error': 'Not authenticated'}

            alert_id = data.get('alert_id')
            if not alert_id:
                emit('alert:error', {'code': 'INVALID_DATA'})
                return {'success': False, 'error': 'alert_id required'}

            user_key = user_info['user_key']
            account_key = user_info['account_key']

            alerts_repo = get_collection('alerts')
            if alerts_repo is None:
                emit('alert:error', {'code': 'SERVICE_UNAVAILABLE'})
                return {'success': False, 'error': 'Service unavailable'}

            try:
                result = alerts_repo.update(
                    {'alert_id': alert_id, 'account_key': account_key},
                    {
                        'acknowledged': True,
                        'acknowledged_by': user_key,
                        'acknowledged_at': datetime.utcnow()
                    }
                )

                if result and getattr(result, 'modified_count', 0) > 0:
                    EventEmitter.emit_to_account(
                        account_key,
                        EventEmitter.ALERT_ACKNOWLEDGED,
                        {'alert_id': alert_id, 'acknowledged_by': user_key}
                    )

                    try:
                        unack_count = alerts_repo.collection.count_documents({
                            'account_key': account_key,
                            'acknowledged': False
                        })
                        EventEmitter.update_alert_count(account_key, unack_count)
                    except:
                        pass

                    return {'success': True, 'alert_id': alert_id}
                else:
                    return {'success': False, 'error': 'Alert not found'}

            except Exception as e:
                logger.error(f"alert:acknowledge error: {e}")
                return {'success': False, 'error': str(e)}

        @self.socketio.on('alert:acknowledge_all')
        def handle_alert_acknowledge_all(data=None):
            """Acknowledge all alerts."""
            user_info = self._get_user_from_socket()
            if not user_info:
                return {'success': False, 'error': 'Not authenticated'}

            user_key = user_info['user_key']
            account_key = user_info['account_key']

            alerts_repo = get_collection('alerts')
            if alerts_repo is None:
                return {'success': False, 'error': 'Service unavailable'}

            try:
                result = alerts_repo.collection.update_many(
                    {'account_key': account_key, 'acknowledged': False},
                    {'$set': {
                        'acknowledged': True,
                        'acknowledged_by': user_key,
                        'acknowledged_at': datetime.utcnow()
                    }}
                )

                count = result.modified_count if result else 0

                EventEmitter.emit_to_account(
                    account_key,
                    'alert:acknowledged_all',
                    {'acknowledged_by': user_key, 'count': count}
                )
                EventEmitter.update_alert_count(account_key, 0)

                return {'success': True, 'count': count}

            except Exception as e:
                logger.error(f"alert:acknowledge_all error: {e}")
                return {'success': False, 'error': str(e)}

        @self.socketio.on('alert:dismiss')
        def handle_alert_dismiss(data):
            """Dismiss an alert."""
            user_info = self._get_user_from_socket()
            if not user_info:
                return {'success': False, 'error': 'Not authenticated'}

            alert_id = data.get('alert_id')
            if not alert_id:
                return {'success': False, 'error': 'alert_id required'}

            user_key = user_info['user_key']
            account_key = user_info['account_key']

            alerts_repo = get_collection('alerts')
            if alerts_repo is None:
                return {'success': False, 'error': 'Service unavailable'}

            try:
                result = alerts_repo.delete({
                    'alert_id': alert_id,
                    'account_key': account_key
                })

                if result and getattr(result, 'deleted_count', 0) > 0:
                    EventEmitter.emit_to_account(
                        account_key,
                        EventEmitter.ALERT_DELETED,
                        {'alert_id': alert_id, 'deleted_by': user_key}
                    )

                    try:
                        unack_count = alerts_repo.collection.count_documents({
                            'account_key': account_key,
                            'acknowledged': False
                        })
                        EventEmitter.update_alert_count(account_key, unack_count)
                    except:
                        pass

                    return {'success': True, 'alert_id': alert_id}
                else:
                    return {'success': False, 'error': 'Alert not found'}

            except Exception as e:
                logger.error(f"alert:dismiss error: {e}")
                return {'success': False, 'error': str(e)}

        @self.socketio.on('alert:get_count')
        def handle_alert_get_count(data=None):
            """Get unacknowledged alert count."""
            user_info = self._get_user_from_socket()
            if not user_info:
                return {'success': False, 'error': 'Not authenticated'}

            alerts_repo = get_collection('alerts')
            if alerts_repo is None:
                return {'success': False, 'error': 'Service unavailable'}

            try:
                count = alerts_repo.collection.count_documents({
                    'account_key': user_info['account_key'],
                    'acknowledged': False
                })
                return {'success': True, 'count': count}
            except Exception as e:
                return {'success': False, 'error': str(e)}

        # =====================================================================
        # Presence Events
        # =====================================================================

        @self.socketio.on('presence:update')
        def handle_presence_update(data):
            """Handle presence status update."""
            user_info = self._get_user_from_socket()
            if not user_info:
                return

            status = data.get('status', 'online')
            if status not in ['online', 'away', 'busy', 'offline']:
                status = 'online'

            EventEmitter.notify_presence(
                user_info['user_key'],
                status,
                user_info['account_key']
            )

        # =====================================================================
        # Subscription Events
        # =====================================================================

        @self.socketio.on('subscribe')
        def handle_subscribe(data):
            """Subscribe to a channel."""
            user_info = self._get_user_from_socket()
            if not user_info:
                emit('error', {'code': 'UNAUTHORIZED'})
                return

            channel = data.get('channel')
            if not channel:
                emit('error', {'code': 'INVALID_DATA'})
                return

            if channel.startswith(f"account:{user_info['account_key']}"):
                join_room(channel)
                emit('subscribed', {'channel': channel})
            else:
                emit('error', {'code': 'FORBIDDEN'})

        @self.socketio.on('unsubscribe')
        def handle_unsubscribe(data):
            """Unsubscribe from a channel."""
            channel = data.get('channel')
            if channel:
                leave_room(channel)
                emit('unsubscribed', {'channel': channel})

        # =====================================================================
        # Ping/Pong
        # =====================================================================

        @self.socketio.on('ping')
        def handle_ping(data=None):
            """Handle ping."""
            emit('pong', {'timestamp': datetime.utcnow().isoformat()})

    def _authenticate(self, token: str) -> Optional[Dict]:
        """Authenticate WebSocket connection."""
        if not token:
            return None
        try:
            return AuthSecurity.decode_token(token)
        except Exception as e:
            logger.debug(f"WS auth error: {e}")
            return None

    def _get_user_from_socket(self, socket_id: str = None) -> Optional[Dict]:
        """Get user info from socket."""
        from flask import request
        sid = socket_id or request.sid
        return self.connected_users.get(sid)

    def _send_pending_events(self, user_key: str, account_key: str):
        """Send pending notifications and alerts."""
        try:
            notification_repo = get_collection('notification')
            if notification_repo is not None:
                try:
                    unread_count = notification_repo.collection.count_documents({
                        'user_key': user_key,
                        'read': False
                    })
                    EventEmitter.update_notification_count(user_key, unread_count)
                except:
                    pass

            alerts_repo = get_collection('alerts')
            if alerts_repo is not None:
                try:
                    unack_count = alerts_repo.collection.count_documents({
                        'account_key': account_key,
                        'acknowledged': False
                    })
                    EventEmitter.update_alert_count(account_key, unack_count)
                except:
                    pass

        except Exception as e:
            logger.error(f"send_pending_events error: {e}")

    # =========================================================================
    # Public API
    # =========================================================================

    def emit_notification(self, user_key: str, notification: Dict[str, Any]):
        """Emit notification to user."""
        return EventEmitter.notify_user(user_key, notification)

    def emit_alert(self, account_key: str, alert: Dict[str, Any]):
        """Emit alert to account."""
        return EventEmitter.notify_account_alert(account_key, alert)

    def emit_task_update(self, account_key: str, task_id: str, update: Dict[str, Any]):
        """Emit task update."""
        return EventEmitter.stream_task_update(account_key, task_id, update)

    def emit_pond_update(self, account_key: str, pond_id: str, update: Dict[str, Any]):
        """Emit pond update."""
        return EventEmitter.stream_pond_update(account_key, pond_id, update)


# Singleton instance
_hub_instance: Optional[WebSocketHub] = None


def get_websocket_hub() -> WebSocketHub:
    """Get WebSocket hub singleton."""
    global _hub_instance
    if _hub_instance is None:
        _hub_instance = WebSocketHub()
    return _hub_instance


def init_websocket_hub(app: Flask, socketio: SocketIO) -> WebSocketHub:
    """Initialize WebSocket hub."""
    hub = get_websocket_hub()
    hub.init_app(app, socketio)
    return hub

