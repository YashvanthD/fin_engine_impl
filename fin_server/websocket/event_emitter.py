"""Centralized Event Emitter for real-time WebSocket communication.

This module provides a singleton EventEmitter that can be used throughout
the application to emit events to connected WebSocket clients.

Usage:
    from fin_server.websocket.event_emitter import EventEmitter

    # Emit to a specific user
    EventEmitter.emit_to_user(user_key, 'notification:new', data)

    # Emit to all users in an account
    EventEmitter.emit_to_account(account_key, 'alert:new', data)

    # Emit to a specific room
    EventEmitter.emit_to_room(room_id, 'message:new', data)
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Will be set when WebSocket hub initializes
_socketio = None
_connected_users: Dict[str, Dict[str, Any]] = {}
_user_sockets: Dict[str, List[str]] = {}


def set_socketio(socketio_instance):
    """Set the Socket.IO instance for the event emitter."""
    global _socketio
    _socketio = socketio_instance
    logger.debug("EventEmitter initialized with Socket.IO instance")


def set_user_tracking(connected_users: Dict, user_sockets: Dict):
    """Set user tracking dictionaries."""
    global _connected_users, _user_sockets
    _connected_users = connected_users
    _user_sockets = user_sockets


class EventEmitter:
    """Centralized event emitter for all real-time events."""

    # =========================================================================
    # Event Type Constants
    # =========================================================================

    # Notification Events
    NOTIFICATION_NEW = 'notification:new'
    NOTIFICATION_READ = 'notification:read'
    NOTIFICATION_READ_ALL = 'notification:read_all'
    NOTIFICATION_DELETED = 'notification:deleted'
    NOTIFICATION_COUNT = 'notification:count'

    # Alert Events
    ALERT_NEW = 'alert:new'
    ALERT_ACKNOWLEDGED = 'alert:acknowledged'
    ALERT_DELETED = 'alert:deleted'
    ALERT_COUNT = 'alert:count'

    # Chat Events
    MESSAGE_NEW = 'message:new'
    MESSAGE_DELIVERED = 'message:delivered'
    MESSAGE_READ = 'message:read'
    MESSAGE_DELETED = 'message:deleted'
    MESSAGE_EDITED = 'message:edited'
    MESSAGE_REACTION = 'message:reaction'
    TYPING_START = 'typing:start'
    TYPING_STOP = 'typing:stop'

    # Presence Events
    PRESENCE_ONLINE = 'presence:online'
    PRESENCE_OFFLINE = 'presence:offline'
    PRESENCE_AWAY = 'presence:away'
    PRESENCE_BUSY = 'presence:busy'

    # Stream Events (real-time data updates)
    STREAM_DATA = 'stream:data'
    STREAM_TASK_UPDATE = 'stream:task_update'
    STREAM_POND_UPDATE = 'stream:pond_update'
    STREAM_EXPENSE_UPDATE = 'stream:expense_update'
    STREAM_SAMPLING_UPDATE = 'stream:sampling_update'

    # =========================================================================
    # Emit Methods
    # =========================================================================

    @staticmethod
    def emit_to_user(user_key: str, event: str, data: Dict[str, Any]) -> bool:
        """Emit event to all connected devices of a specific user.

        Args:
            user_key: The target user's key
            event: Event name (e.g., 'notification:new')
            data: Event payload

        Returns:
            True if event was emitted to at least one socket
        """
        logger.debug(f"EVENT_EMITTER: emit_to_user called - user={user_key}, event={event}")

        if not _socketio:
            logger.error(f"EVENT_EMITTER: Socket.IO NOT initialized, cannot emit {event} to user {user_key}")
            return False

        sockets = _user_sockets.get(user_key, [])
        logger.debug(f"EVENT_EMITTER: User {user_key} has {len(sockets)} connected socket(s)")

        if not sockets:
            logger.warning(f"EVENT_EMITTER: User {user_key} not connected, event {event} not delivered")
            # TODO: Queue for offline delivery
            return False

        # Add metadata
        payload = {
            **data,
            '_event': event,
            '_timestamp': datetime.utcnow().isoformat(),
            '_target': 'user',
            '_target_id': user_key
        }

        emitted_count = 0
        for sid in sockets:
            try:
                _socketio.emit(event, payload, room=sid)
                emitted_count += 1
                logger.debug(f"EVENT_EMITTER: Emitted '{event}' to socket {sid}")
            except Exception as e:
                logger.error(f"EVENT_EMITTER: Error emitting {event} to socket {sid}: {e}")

        logger.debug(f"EVENT_EMITTER: Successfully emitted '{event}' to {emitted_count}/{len(sockets)} sockets for user {user_key}")
        return emitted_count > 0

    @staticmethod
    def emit_to_account(account_key: str, event: str, data: Dict[str, Any]) -> int:
        """Emit event to all users in an account.

        Args:
            account_key: The target account key
            event: Event name
            data: Event payload

        Returns:
            Number of users the event was emitted to
        """
        logger.debug(f"EVENT_EMITTER: emit_to_account called - account={account_key}, event={event}")

        if not _socketio:
            logger.error(f"EVENT_EMITTER: Socket.IO NOT initialized, cannot emit {event} to account {account_key}")
            return 0

        # Add metadata
        payload = {
            **data,
            '_event': event,
            '_timestamp': datetime.utcnow().isoformat(),
            '_target': 'account',
            '_target_id': account_key
        }

        # Emit to account room
        try:
            _socketio.emit(event, payload, room=account_key)
            logger.debug(f"EVENT_EMITTER: Emitted '{event}' to account room '{account_key}'")
            return 1  # Room-based emit
        except Exception as e:
            logger.error(f"EVENT_EMITTER: Error emitting {event} to account {account_key}: {e}")
            return 0

    @staticmethod
    def emit_to_room(room_id: str, event: str, data: Dict[str, Any], exclude_sender: Optional[str] = None) -> bool:
        """Emit event to all users in a room (e.g., conversation).

        Args:
            room_id: The room identifier
            event: Event name
            data: Event payload
            exclude_sender: Optional user_key to exclude from broadcast

        Returns:
            True if event was emitted
        """
        logger.debug(f"EVENT_EMITTER: emit_to_room called - room={room_id}, event={event}, exclude={exclude_sender}")

        if not _socketio:
            logger.error(f"EVENT_EMITTER: Socket.IO NOT initialized, cannot emit {event} to room {room_id}")
            return False

        payload = {
            **data,
            '_event': event,
            '_timestamp': datetime.utcnow().isoformat(),
            '_target': 'room',
            '_target_id': room_id
        }

        try:
            if exclude_sender:
                # Get sender's sockets to skip
                sender_sockets = _user_sockets.get(exclude_sender, [])
                _socketio.emit(event, payload, room=room_id, skip_sid=sender_sockets)
            else:
                _socketio.emit(event, payload, room=room_id)

            logger.debug(f"Emitted {event} to room {room_id}")
            return True
        except Exception as e:
            logger.error(f"Error emitting {event} to room {room_id}: {e}")
            return False

    @staticmethod
    def broadcast(event: str, data: Dict[str, Any]) -> bool:
        """Broadcast event to all connected clients.

        Args:
            event: Event name
            data: Event payload

        Returns:
            True if event was broadcast
        """
        if not _socketio:
            logger.warning(f"Socket.IO not initialized, cannot broadcast {event}")
            return False

        payload = {
            **data,
            '_event': event,
            '_timestamp': datetime.utcnow().isoformat(),
            '_target': 'broadcast'
        }

        try:
            _socketio.emit(event, payload)
            logger.debug(f"Broadcast {event} to all clients")
            return True
        except Exception as e:
            logger.error(f"Error broadcasting {event}: {e}")
            return False

    # =========================================================================
    # Convenience Methods for Common Events
    # =========================================================================

    @classmethod
    def notify_user(cls, user_key: str, notification: Dict[str, Any]) -> bool:
        """Send a notification to a user.

        Args:
            user_key: Target user
            notification: Notification data with id, title, message, type
        """
        return cls.emit_to_user(user_key, cls.NOTIFICATION_NEW, notification)

    @classmethod
    def notify_account_alert(cls, account_key: str, alert: Dict[str, Any]) -> int:
        """Send an alert to all users in an account.

        Args:
            account_key: Target account
            alert: Alert data with id, title, message, severity, type
        """
        return cls.emit_to_account(account_key, cls.ALERT_NEW, alert)

    @classmethod
    def update_notification_count(cls, user_key: str, unread_count: int) -> bool:
        """Update user's unread notification count."""
        return cls.emit_to_user(user_key, cls.NOTIFICATION_COUNT, {'unread': unread_count})

    @classmethod
    def update_alert_count(cls, account_key: str, unacknowledged_count: int) -> int:
        """Update account's unacknowledged alert count."""
        return cls.emit_to_account(account_key, cls.ALERT_COUNT, {'unacknowledged': unacknowledged_count})

    @classmethod
    def send_message(cls, conversation_id: str, message: Dict[str, Any], sender_key: str = None) -> bool:
        """Send a chat message to a conversation."""
        return cls.emit_to_room(f"conv:{conversation_id}", cls.MESSAGE_NEW, message, exclude_sender=sender_key)

    @classmethod
    def notify_presence(cls, user_key: str, status: str, account_key: str = None) -> bool:
        """Notify about user presence change."""
        event = {
            'online': cls.PRESENCE_ONLINE,
            'offline': cls.PRESENCE_OFFLINE,
            'away': cls.PRESENCE_AWAY,
            'busy': cls.PRESENCE_BUSY
        }.get(status, cls.PRESENCE_ONLINE)

        data = {'user_key': user_key, 'status': status}

        if account_key:
            cls.emit_to_account(account_key, event, data)
        return True

    @classmethod
    def stream_task_update(cls, account_key: str, task_id: str, update: Dict[str, Any]) -> int:
        """Stream a task update to all users in account."""
        return cls.emit_to_account(account_key, cls.STREAM_TASK_UPDATE, {
            'task_id': task_id,
            **update
        })

    @classmethod
    def stream_pond_update(cls, account_key: str, pond_id: str, update: Dict[str, Any]) -> int:
        """Stream a pond update to all users in account."""
        return cls.emit_to_account(account_key, cls.STREAM_POND_UPDATE, {
            'pond_id': pond_id,
            **update
        })

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @staticmethod
    def is_user_online(user_key: str) -> bool:
        """Check if a user is currently connected."""
        return user_key in _user_sockets and len(_user_sockets[user_key]) > 0

    @staticmethod
    def get_online_users(account_key: str = None) -> List[str]:
        """Get list of online users, optionally filtered by account."""
        online = list(_user_sockets.keys())

        if account_key:
            # Filter by account
            online = [
                user_key for user_key in online
                if any(
                    _connected_users.get(sid, {}).get('account_key') == account_key
                    for sid in _user_sockets.get(user_key, [])
                )
            ]

        return online

    @staticmethod
    def get_connection_count() -> int:
        """Get total number of connected sockets."""
        return len(_connected_users)

    @staticmethod
    def get_user_count() -> int:
        """Get total number of connected unique users."""
        return len(_user_sockets)

