"""Centralized WebSocket Hub.

This module integrates with the existing Socket.IO server and adds:
- Notification events
- Alert events
- Stream events (real-time data updates)

It wraps the existing messaging/socket_server.py functionality.
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
    """Centralized WebSocket Hub for all real-time communication."""

    def __init__(self, socketio: SocketIO = None):
        self.socketio = socketio
        self.connected_users: Dict[str, Dict[str, Any]] = {}
        self.user_sockets: Dict[str, list] = {}
        self._initialized = False

    def init_app(self, app: Flask, socketio: SocketIO):
        """Initialize the WebSocket hub with Flask app and Socket.IO instance.

        Args:
            app: Flask application
            socketio: Socket.IO instance
        """
        self.socketio = socketio
        self.app = app

        # Set up event emitter with socketio instance
        set_socketio(socketio)
        set_user_tracking(self.connected_users, self.user_sockets)

        # Register event handlers
        self._register_handlers()

        self._initialized = True
        logger.info("WebSocket Hub initialized")

    def _register_handlers(self):
        """Register all WebSocket event handlers."""

        # =====================================================================
        # Connection Events
        # =====================================================================

        @self.socketio.on('connect')
        def handle_connect(auth=None):
            """Handle new WebSocket connection."""
            from flask import request

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
                emit('error', {'code': 'UNAUTHORIZED', 'message': 'Invalid or missing token'})
                disconnect()
                return False

            user_key = payload.get('user_key')
            account_key = payload.get('account_key')
            socket_id = request.sid

            # Store connection
            self.connected_users[socket_id] = {
                'user_key': user_key,
                'account_key': account_key,
                'connected_at': datetime.utcnow().isoformat(),
                'device_info': {
                    'user_agent': request.headers.get('User-Agent'),
                    'ip': request.remote_addr
                }
            }

            # Track user's sockets (multi-device support)
            if user_key not in self.user_sockets:
                self.user_sockets[user_key] = []
            self.user_sockets[user_key].append(socket_id)

            # Join rooms
            join_room(user_key)      # Personal room
            join_room(account_key)   # Account room

            # Send connection success
            emit('connected', {
                'message': 'Connected to WebSocket Hub',
                'user_key': user_key,
                'socket_id': socket_id,
                'features': ['notifications', 'alerts', 'chat', 'presence', 'streams']
            })

            # Notify others of online status
            EventEmitter.notify_presence(user_key, 'online', account_key)

            # Send pending notifications/alerts
            self._send_pending_events(user_key, account_key)

            logger.info(f"User {user_key} connected (socket: {socket_id})")
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

                # Remove from user's socket list
                if user_key in self.user_sockets:
                    self.user_sockets[user_key] = [
                        s for s in self.user_sockets[user_key] if s != socket_id
                    ]

                    # If no more connections, user is offline
                    if not self.user_sockets[user_key]:
                        del self.user_sockets[user_key]
                        EventEmitter.notify_presence(user_key, 'offline', account_key)

                logger.info(f"User {user_key} disconnected (socket: {socket_id})")

        # =====================================================================
        # Notification Events
        # =====================================================================

        @self.socketio.on('notification:mark_read')
        def handle_notification_mark_read(data):
            """Handle marking notification as read."""
            user_info = self._get_user_from_socket()
            if not user_info:
                emit('error', {'code': 'UNAUTHORIZED', 'message': 'Not authenticated'})
                return

            notification_id = data.get('notification_id')
            if not notification_id:
                emit('error', {'code': 'INVALID_DATA', 'message': 'notification_id required'})
                return

            # Update in database
            notification_repo = get_collection('notification')
            if notification_repo:
                notification_repo.update(
                    {'notification_id': notification_id, 'user_key': user_info['user_key']},
                    {'read': True, 'read_at': datetime.utcnow()}
                )

            # Emit read event to all user's devices
            EventEmitter.emit_to_user(
                user_info['user_key'],
                EventEmitter.NOTIFICATION_READ,
                {'notification_id': notification_id}
            )

        @self.socketio.on('notification:mark_all_read')
        def handle_notification_mark_all_read(data=None):
            """Handle marking all notifications as read."""
            user_info = self._get_user_from_socket()
            if not user_info:
                emit('error', {'code': 'UNAUTHORIZED', 'message': 'Not authenticated'})
                return

            # Update in database
            notification_repo = get_collection('notification')
            if notification_repo:
                notification_repo.update(
                    {'user_key': user_info['user_key'], 'read': False},
                    {'read': True, 'read_at': datetime.utcnow()},
                    multi=True
                )

            # Emit to all user's devices
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
            """Handle acknowledging an alert."""
            user_info = self._get_user_from_socket()
            if not user_info:
                emit('error', {'code': 'UNAUTHORIZED', 'message': 'Not authenticated'})
                return

            alert_id = data.get('alert_id')
            if not alert_id:
                emit('error', {'code': 'INVALID_DATA', 'message': 'alert_id required'})
                return

            # Update in database
            alerts_repo = get_collection('alerts')
            if alerts_repo:
                alerts_repo.update(
                    {'alert_id': alert_id, 'account_key': user_info['account_key']},
                    {
                        'acknowledged': True,
                        'acknowledged_by': user_info['user_key'],
                        'acknowledged_at': datetime.utcnow()
                    }
                )

            # Emit to all account users
            EventEmitter.emit_to_account(
                user_info['account_key'],
                EventEmitter.ALERT_ACKNOWLEDGED,
                {
                    'alert_id': alert_id,
                    'acknowledged_by': user_info['user_key']
                }
            )

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
            """Subscribe to a room/channel for updates."""
            from flask import request

            user_info = self._get_user_from_socket()
            if not user_info:
                emit('error', {'code': 'UNAUTHORIZED', 'message': 'Not authenticated'})
                return

            channel = data.get('channel')
            if not channel:
                emit('error', {'code': 'INVALID_DATA', 'message': 'channel required'})
                return

            # Validate channel access
            # For now, allow subscription to account-scoped channels
            if channel.startswith(f"account:{user_info['account_key']}"):
                join_room(channel)
                emit('subscribed', {'channel': channel})
                logger.debug(f"User {user_info['user_key']} subscribed to {channel}")
            else:
                emit('error', {'code': 'FORBIDDEN', 'message': 'Cannot subscribe to this channel'})

        @self.socketio.on('unsubscribe')
        def handle_unsubscribe(data):
            """Unsubscribe from a room/channel."""
            from flask import request

            channel = data.get('channel')
            if channel:
                leave_room(channel)
                emit('unsubscribed', {'channel': channel})

        # =====================================================================
        # Ping/Pong for connection health
        # =====================================================================

        @self.socketio.on('ping')
        def handle_ping(data=None):
            """Handle ping from client."""
            emit('pong', {'timestamp': datetime.utcnow().isoformat()})

    def _authenticate(self, token: str) -> Optional[Dict]:
        """Authenticate a WebSocket connection."""
        if not token:
            return None

        try:
            payload = AuthSecurity.decode_token(token)
            return payload
        except Exception as e:
            logger.warning(f"WebSocket authentication failed: {e}")
            return None

    def _get_user_from_socket(self, socket_id: str = None) -> Optional[Dict]:
        """Get user info from socket connection."""
        from flask import request
        sid = socket_id or request.sid
        return self.connected_users.get(sid)

    def _send_pending_events(self, user_key: str, account_key: str):
        """Send pending notifications and alerts to user on connect."""
        try:
            # Get unread notification count
            notification_repo = get_collection('notification')
            if notification_repo:
                try:
                    unread_count = notification_repo.collection.count_documents({
                        'user_key': user_key,
                        'read': False
                    })
                    EventEmitter.update_notification_count(user_key, unread_count)
                except Exception:
                    pass

            # Get unacknowledged alert count
            alerts_repo = get_collection('alerts')
            if alerts_repo:
                try:
                    unack_count = alerts_repo.collection.count_documents({
                        'account_key': account_key,
                        'acknowledged': False
                    })
                    EventEmitter.update_alert_count(account_key, unack_count)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error sending pending events: {e}")

    # =========================================================================
    # Public API for emitting events from routes
    # =========================================================================

    def emit_notification(self, user_key: str, notification: Dict[str, Any]):
        """Emit a notification to a user."""
        return EventEmitter.notify_user(user_key, notification)

    def emit_alert(self, account_key: str, alert: Dict[str, Any]):
        """Emit an alert to all users in an account."""
        return EventEmitter.notify_account_alert(account_key, alert)

    def emit_task_update(self, account_key: str, task_id: str, update: Dict[str, Any]):
        """Emit a task update to all users in an account."""
        return EventEmitter.stream_task_update(account_key, task_id, update)

    def emit_pond_update(self, account_key: str, pond_id: str, update: Dict[str, Any]):
        """Emit a pond update to all users in an account."""
        return EventEmitter.stream_pond_update(account_key, pond_id, update)


# Singleton instance
_hub_instance: Optional[WebSocketHub] = None


def get_websocket_hub() -> WebSocketHub:
    """Get the WebSocket hub singleton instance."""
    global _hub_instance
    if _hub_instance is None:
        _hub_instance = WebSocketHub()
    return _hub_instance


def init_websocket_hub(app: Flask, socketio: SocketIO) -> WebSocketHub:
    """Initialize the WebSocket hub with Flask app."""
    hub = get_websocket_hub()
    hub.init_app(app, socketio)
    return hub

