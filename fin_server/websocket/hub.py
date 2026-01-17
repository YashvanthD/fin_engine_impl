"""Centralized WebSocket Hub.

This module integrates with the existing Socket.IO server and adds:
- Notification events
- Alert events
- Stream events (real-time data updates)
- Chat/Messaging events (real-time chat)

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
        self._chat_handler = None

    def init_app(self, app: Flask, socketio: SocketIO):
        """Initialize the WebSocket hub with Flask app and Socket.IO instance.

        Args:
            app: Flask application
            socketio: Socket.IO instance
        """
        print("=" * 60)
        print("WEBSOCKET HUB: Starting initialization...")
        print(f"WEBSOCKET HUB: Flask app: {app.name}")
        print(f"WEBSOCKET HUB: SocketIO instance: {socketio}")
        print(f"WEBSOCKET HUB: SocketIO async_mode: {getattr(socketio, 'async_mode', 'unknown')}")

        logger.info("=" * 60)
        logger.info("WEBSOCKET HUB: Starting initialization...")
        logger.info(f"WEBSOCKET HUB: Flask app: {app.name}")
        logger.info(f"WEBSOCKET HUB: SocketIO instance: {socketio}")
        logger.info(f"WEBSOCKET HUB: SocketIO async_mode: {getattr(socketio, 'async_mode', 'unknown')}")

        self.socketio = socketio
        self.app = app

        # Set up event emitter with socketio instance
        set_socketio(socketio)
        set_user_tracking(self.connected_users, self.user_sockets)
        print("WEBSOCKET HUB: ✓ Event emitter configured")
        logger.info("WEBSOCKET HUB: ✓ Event emitter configured")

        # Register event handlers
        self._register_handlers()
        print("WEBSOCKET HUB: ✓ Event handlers registered")
        logger.info("WEBSOCKET HUB: ✓ Event handlers registered")

        # Initialize chat handler
        self._init_chat_handler()
        print("WEBSOCKET HUB: ✓ Chat handler initialized")
        logger.info("WEBSOCKET HUB: ✓ Chat handler initialized")

        self._initialized = True
        print("=" * 60)
        print("WEBSOCKET HUB: ★★★ INITIALIZATION COMPLETE ★★★")
        print("=" * 60)
        print("WEBSOCKET HUB: Listening for events:")
        print("  - connect / disconnect")
        print("  - chat:send, chat:read, chat:typing, chat:edit, chat:delete")
        print("=" * 60)

        logger.info("=" * 60)
        logger.info("WEBSOCKET HUB: ★★★ INITIALIZATION COMPLETE ★★★")
        logger.info("=" * 60)
        logger.info("WEBSOCKET HUB: Listening for events:")
        logger.info("  - connect / disconnect")
        logger.info("  - notification:mark_read, notification:mark_all_read")
        logger.info("  - alert:acknowledge")
        logger.info("  - presence:update")
        logger.info("  - subscribe / unsubscribe")
        logger.info("  - ping")
        logger.info("  - chat:send, chat:read, chat:typing, chat:edit, chat:delete")
        logger.info("  - chat:conversation:create, chat:conversation:join, chat:conversation:leave")
        logger.info("=" * 60)

    def _init_chat_handler(self):
        """Initialize the chat handler for real-time messaging."""
        try:
            from fin_server.websocket.handlers.chat_handler import init_chat_handler
            self._chat_handler = init_chat_handler(
                self.socketio,
                self.connected_users,
                self.user_sockets
            )
            logger.info("WEBSOCKET: Chat handler integrated with WebSocket Hub")
        except Exception as e:
            logger.error(f"WEBSOCKET: Failed to initialize chat handler: {e}")

    def _register_handlers(self):
        """Register all WebSocket event handlers."""

        print("WEBSOCKET: Registering event handlers...")
        logger.info("WEBSOCKET: Registering event handlers...")

        # Debug: Log all incoming events with a catch-all handler
        @self.socketio.on_error_default
        def default_error_handler(e):
            print(f"WEBSOCKET ERROR: {e}")
            logger.error(f"WEBSOCKET ERROR: {e}")

        # Catch-all event handler for debugging - logs ANY event received
        @self.socketio.on('*')
        def catch_all(event, data=None):
            print(f"WEBSOCKET CATCH-ALL: Received event '{event}' with data: {data}")
            logger.info(f"WEBSOCKET CATCH-ALL: Received event '{event}' with data: {data}")

        print("WEBSOCKET: ✓ Registered catch-all event handler")
        logger.info("WEBSOCKET: ✓ Registered catch-all event handler")

        # =====================================================================
        # Connection Events
        # =====================================================================

        @self.socketio.on('connect')
        def handle_connect(auth=None):
            """Handle new WebSocket connection."""
            from flask import request

            print("=" * 60)
            print("WEBSOCKET: ★★★ NEW CONNECTION ATTEMPT ★★★")
            print(f"WEBSOCKET: Auth data received: {auth}")
            print(f"WEBSOCKET: Request SID: {getattr(request, 'sid', 'N/A')}")
            print(f"WEBSOCKET: Remote addr: {request.remote_addr}")

            logger.info("=" * 60)
            logger.info("WEBSOCKET: ★★★ NEW CONNECTION ATTEMPT ★★★")
            logger.info(f"WEBSOCKET: Auth data received: {auth}")
            logger.info(f"WEBSOCKET: Request SID: {getattr(request, 'sid', 'N/A')}")
            logger.info(f"WEBSOCKET: Remote addr: {request.remote_addr}")
            logger.info(f"WEBSOCKET: Headers: {dict(request.headers)}")

            # Get token from auth data or headers
            token = None
            if auth and isinstance(auth, dict):
                token = auth.get('token')
                logger.info(f"WEBSOCKET: Token from auth dict: {token[:20] if token else 'None'}...")

            if not token:
                token = request.headers.get('Authorization', '').replace('Bearer ', '')
                if token:
                    logger.info(f"WEBSOCKET: Token from Authorization header: {token[:20]}...")

            if not token:
                token = request.args.get('token', '')
                if token:
                    logger.info(f"WEBSOCKET: Token from query param: {token[:20]}...")

            if not token:
                logger.warning("WEBSOCKET: No token found in auth, headers, or query params")

            # Authenticate
            payload = self._authenticate(token)
            if not payload:
                logger.error("WEBSOCKET: Authentication FAILED - invalid or missing token")
                emit('error', {'code': 'UNAUTHORIZED', 'message': 'Invalid or missing token'})
                disconnect()
                return False

            user_key = payload.get('user_key')
            account_key = payload.get('account_key')
            socket_id = request.sid

            logger.info(f"WEBSOCKET: Authentication SUCCESS")
            logger.info(f"WEBSOCKET: user_key={user_key}, account_key={account_key}, socket_id={socket_id}")

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

            logger.info(f"WEBSOCKET: User {user_key} now has {len(self.user_sockets[user_key])} active connection(s)")
            logger.info(f"WEBSOCKET: Total connected users: {len(self.connected_users)}")

            # Join rooms
            join_room(user_key)      # Personal room
            join_room(account_key)   # Account room
            logger.info(f"WEBSOCKET: Joined rooms: [{user_key}, {account_key}]")

            # Send connection success
            emit('connected', {
                'message': 'Connected to WebSocket Hub',
                'user_key': user_key,
                'socket_id': socket_id,
                'features': ['notifications', 'alerts', 'chat', 'presence', 'streams']
            })
            logger.info(f"WEBSOCKET: Sent 'connected' event to client")

            # Notify others of online status
            EventEmitter.notify_presence(user_key, 'online', account_key)

            # Initialize chat for this user (join conversation rooms, update presence)
            if self._chat_handler:
                self._chat_handler.on_user_connected(user_key, account_key, socket_id)
                logger.info(f"WEBSOCKET: Chat handler initialized for user")

            # Send pending notifications/alerts
            self._send_pending_events(user_key, account_key)

            logger.info(f"WEBSOCKET: Connection setup COMPLETE for {user_key}")
            logger.info("=" * 60)
            return True

        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle WebSocket disconnection."""
            from flask import request

            socket_id = request.sid
            logger.info(f"WEBSOCKET: Disconnect event - socket_id={socket_id}")
            user_info = self.connected_users.pop(socket_id, None)

            if user_info:
                user_key = user_info.get('user_key')
                account_key = user_info.get('account_key')
                logger.info(f"WEBSOCKET: User {user_key} disconnecting...")

                # Remove from user's socket list
                if user_key in self.user_sockets:
                    self.user_sockets[user_key] = [
                        s for s in self.user_sockets[user_key] if s != socket_id
                    ]

                    # If no more connections, user is offline
                    if not self.user_sockets[user_key]:
                        del self.user_sockets[user_key]
                        logger.info(f"WEBSOCKET: User {user_key} is now OFFLINE (no more connections)")
                        EventEmitter.notify_presence(user_key, 'offline', account_key)

                        # Notify chat handler of user going offline
                        if self._chat_handler:
                            self._chat_handler.on_user_disconnected(user_key, account_key)
                    else:
                        logger.info(f"WEBSOCKET: User {user_key} still has {len(self.user_sockets[user_key])} connection(s)")

                logger.info(f"WEBSOCKET: Disconnect COMPLETE for {user_key} (socket: {socket_id})")
                logger.info(f"WEBSOCKET: Total connected users: {len(self.connected_users)}")
            else:
                logger.warning(f"WEBSOCKET: Disconnect - no user info found for socket {socket_id}")

        # =====================================================================
        # Notification Events
        # =====================================================================

        @self.socketio.on('notification:mark_read')
        def handle_notification_mark_read(data):
            """Handle marking notification as read."""
            logger.info(f"WEBSOCKET: notification:mark_read received - data={data}")
            user_info = self._get_user_from_socket()
            if not user_info:
                logger.warning("WEBSOCKET: notification:mark_read - user not authenticated")
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
            """Handle acknowledging an alert via WebSocket.

            Data:
                alert_id: str - Alert ID to acknowledge

            Response:
                Callback with {success: bool, alert_id: str}

            Emits:
                alert:acknowledged - To all account users
                alert:count - Updated count to all account users
            """
            from flask import request
            socket_id = request.sid

            print(f"ALERT_HANDLER: alert:acknowledge received from {socket_id}")
            print(f"ALERT_HANDLER: Data: {data}")

            user_info = self._get_user_from_socket()
            if not user_info:
                print("ALERT_HANDLER: Unauthorized - no user info")
                emit('alert:error', {'code': 'UNAUTHORIZED', 'message': 'Not authenticated'})
                return {'success': False, 'error': 'Not authenticated'}

            alert_id = data.get('alert_id')
            if not alert_id:
                print("ALERT_HANDLER: Missing alert_id")
                emit('alert:error', {'code': 'INVALID_DATA', 'message': 'alert_id required'})
                return {'success': False, 'error': 'alert_id required'}

            user_key = user_info['user_key']
            account_key = user_info['account_key']
            print(f"ALERT_HANDLER: User {user_key} acknowledging alert {alert_id}")

            # Update in database
            alerts_repo = get_collection('alerts')
            if alerts_repo is None:
                print("ALERT_HANDLER: Alerts repository not available")
                emit('alert:error', {'code': 'SERVICE_UNAVAILABLE', 'message': 'Alert service unavailable'})
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
                    print(f"ALERT_HANDLER: Alert {alert_id} acknowledged successfully")

                    # Emit to all account users
                    EventEmitter.emit_to_account(
                        account_key,
                        EventEmitter.ALERT_ACKNOWLEDGED,
                        {
                            'alert_id': alert_id,
                            'acknowledged_by': user_key,
                            'acknowledged_at': datetime.utcnow().isoformat()
                        }
                    )

                    # Update unacknowledged count
                    try:
                        unack_count = alerts_repo.collection.count_documents({
                            'account_key': account_key,
                            'acknowledged': False
                        })
                        EventEmitter.update_alert_count(account_key, unack_count)
                        print(f"ALERT_HANDLER: Updated alert count to {unack_count}")
                    except Exception as e:
                        print(f"ALERT_HANDLER: Error updating count: {e}")

                    return {'success': True, 'alert_id': alert_id}
                else:
                    print(f"ALERT_HANDLER: Alert {alert_id} not found or already acknowledged")
                    return {'success': False, 'error': 'Alert not found or already acknowledged'}

            except Exception as e:
                print(f"ALERT_HANDLER: Error acknowledging alert: {e}")
                emit('alert:error', {'code': 'ERROR', 'message': str(e)})
                return {'success': False, 'error': str(e)}

        @self.socketio.on('alert:acknowledge_all')
        def handle_alert_acknowledge_all(data=None):
            """Handle acknowledging all alerts via WebSocket.

            Response:
                Callback with {success: bool, count: int}

            Emits:
                alert:acknowledged_all - To all account users
                alert:count - Updated count (0) to all account users
            """
            from flask import request
            socket_id = request.sid

            print(f"ALERT_HANDLER: alert:acknowledge_all received from {socket_id}")

            user_info = self._get_user_from_socket()
            if not user_info:
                print("ALERT_HANDLER: Unauthorized - no user info")
                emit('alert:error', {'code': 'UNAUTHORIZED', 'message': 'Not authenticated'})
                return {'success': False, 'error': 'Not authenticated'}

            user_key = user_info['user_key']
            account_key = user_info['account_key']
            print(f"ALERT_HANDLER: User {user_key} acknowledging all alerts for account {account_key}")

            alerts_repo = get_collection('alerts')
            if alerts_repo is None:
                print("ALERT_HANDLER: Alerts repository not available")
                emit('alert:error', {'code': 'SERVICE_UNAVAILABLE', 'message': 'Alert service unavailable'})
                return {'success': False, 'error': 'Service unavailable'}

            try:
                # Update all unacknowledged alerts
                result = alerts_repo.collection.update_many(
                    {'account_key': account_key, 'acknowledged': False},
                    {'$set': {
                        'acknowledged': True,
                        'acknowledged_by': user_key,
                        'acknowledged_at': datetime.utcnow()
                    }}
                )

                count = result.modified_count if result else 0
                print(f"ALERT_HANDLER: Acknowledged {count} alerts")

                # Emit to all account users
                EventEmitter.emit_to_account(
                    account_key,
                    'alert:acknowledged_all',
                    {
                        'acknowledged_by': user_key,
                        'count': count,
                        'acknowledged_at': datetime.utcnow().isoformat()
                    }
                )

                # Update count to 0
                EventEmitter.update_alert_count(account_key, 0)

                return {'success': True, 'count': count}

            except Exception as e:
                print(f"ALERT_HANDLER: Error acknowledging all alerts: {e}")
                emit('alert:error', {'code': 'ERROR', 'message': str(e)})
                return {'success': False, 'error': str(e)}

        @self.socketio.on('alert:dismiss')
        def handle_alert_dismiss(data):
            """Handle dismissing/deleting an alert via WebSocket.

            Data:
                alert_id: str - Alert ID to dismiss

            Response:
                Callback with {success: bool, alert_id: str}

            Emits:
                alert:deleted - To all account users
                alert:count - Updated count to all account users
            """
            from flask import request
            socket_id = request.sid

            print(f"ALERT_HANDLER: alert:dismiss received from {socket_id}")
            print(f"ALERT_HANDLER: Data: {data}")

            user_info = self._get_user_from_socket()
            if not user_info:
                emit('alert:error', {'code': 'UNAUTHORIZED', 'message': 'Not authenticated'})
                return {'success': False, 'error': 'Not authenticated'}

            alert_id = data.get('alert_id')
            if not alert_id:
                emit('alert:error', {'code': 'INVALID_DATA', 'message': 'alert_id required'})
                return {'success': False, 'error': 'alert_id required'}

            user_key = user_info['user_key']
            account_key = user_info['account_key']
            print(f"ALERT_HANDLER: User {user_key} dismissing alert {alert_id}")

            alerts_repo = get_collection('alerts')
            if alerts_repo is None:
                emit('alert:error', {'code': 'SERVICE_UNAVAILABLE', 'message': 'Alert service unavailable'})
                return {'success': False, 'error': 'Service unavailable'}

            try:
                result = alerts_repo.delete({
                    'alert_id': alert_id,
                    'account_key': account_key
                })

                if result and getattr(result, 'deleted_count', 0) > 0:
                    print(f"ALERT_HANDLER: Alert {alert_id} dismissed successfully")

                    # Emit to all account users
                    EventEmitter.emit_to_account(
                        account_key,
                        EventEmitter.ALERT_DELETED,
                        {'alert_id': alert_id, 'deleted_by': user_key}
                    )

                    # Update count
                    try:
                        unack_count = alerts_repo.collection.count_documents({
                            'account_key': account_key,
                            'acknowledged': False
                        })
                        EventEmitter.update_alert_count(account_key, unack_count)
                    except Exception:
                        pass

                    return {'success': True, 'alert_id': alert_id}
                else:
                    return {'success': False, 'error': 'Alert not found'}

            except Exception as e:
                print(f"ALERT_HANDLER: Error dismissing alert: {e}")
                emit('alert:error', {'code': 'ERROR', 'message': str(e)})
                return {'success': False, 'error': str(e)}

        @self.socketio.on('alert:get_count')
        def handle_alert_get_count(data=None):
            """Get current unacknowledged alert count.

            Response:
                Callback with {success: bool, count: int}
            """
            user_info = self._get_user_from_socket()
            if not user_info:
                return {'success': False, 'error': 'Not authenticated'}

            account_key = user_info['account_key']

            alerts_repo = get_collection('alerts')
            if alerts_repo is None:
                return {'success': False, 'error': 'Service unavailable'}

            try:
                count = alerts_repo.collection.count_documents({
                    'account_key': account_key,
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

