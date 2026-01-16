"""Notification handler for WebSocket events.

This module handles notification-related WebSocket events and provides
helper functions to emit notifications via WebSocket.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fin_server.websocket.event_emitter import EventEmitter
from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.generator import generate_uuid_hex
from fin_server.utils.time_utils import get_time_date_dt

logger = logging.getLogger(__name__)


class NotificationHandler:
    """Handler for notification WebSocket events."""

    @staticmethod
    def create_and_emit(
        account_key: str,
        target_user_key: str,
        title: str,
        message: str,
        notification_type: str = 'info',
        priority: str = 'normal',
        data: Dict[str, Any] = None,
        link: str = None,
        created_by: str = None
    ) -> Optional[str]:
        """Create a notification in DB and emit via WebSocket.

        Args:
            account_key: Account key
            target_user_key: User to notify
            title: Notification title
            message: Notification message
            notification_type: Type (info, warning, error, success)
            priority: Priority (low, normal, high)
            data: Additional data
            link: Link to related resource
            created_by: User who created the notification

        Returns:
            Notification ID if successful, None otherwise
        """
        notification_repo = get_collection('notification')
        if not notification_repo:
            logger.error("Notification repository not available")
            return None

        # Create notification document
        notification_id = generate_uuid_hex(24)
        now = get_time_date_dt(include_time=True)

        notification_doc = {
            '_id': notification_id,
            'notification_id': notification_id,
            'account_key': account_key,
            'user_key': target_user_key,
            'title': title,
            'message': message,
            'type': notification_type,
            'priority': priority,
            'data': data or {},
            'link': link,
            'read': False,
            'delivered': False,
            'created_by': created_by,
            'created_at': now,
            'updated_at': now
        }

        try:
            # Save to database
            notification_repo.create(notification_doc)

            # Emit via WebSocket
            EventEmitter.notify_user(target_user_key, {
                'notification_id': notification_id,
                'title': title,
                'message': message,
                'type': notification_type,
                'priority': priority,
                'data': data or {},
                'link': link,
                'created_at': now.isoformat() if hasattr(now, 'isoformat') else str(now)
            })

            # Update unread count
            try:
                unread_count = notification_repo.collection.count_documents({
                    'user_key': target_user_key,
                    'read': False
                })
                EventEmitter.update_notification_count(target_user_key, unread_count)
            except Exception:
                pass

            logger.info(f"Notification {notification_id} created and emitted to {target_user_key}")
            return notification_id

        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return None

    @staticmethod
    def mark_read_and_emit(notification_id: str, user_key: str) -> bool:
        """Mark notification as read and emit update via WebSocket.

        Args:
            notification_id: Notification ID
            user_key: User key

        Returns:
            True if successful
        """
        notification_repo = get_collection('notification')
        if not notification_repo:
            return False

        try:
            result = notification_repo.update(
                {'notification_id': notification_id, 'user_key': user_key},
                {
                    'read': True,
                    'read_at': get_time_date_dt(include_time=True),
                    'updated_at': get_time_date_dt(include_time=True)
                }
            )

            if result.modified_count > 0:
                # Emit via WebSocket
                EventEmitter.emit_to_user(user_key, EventEmitter.NOTIFICATION_READ, {
                    'notification_id': notification_id
                })

                # Update unread count
                try:
                    unread_count = notification_repo.collection.count_documents({
                        'user_key': user_key,
                        'read': False
                    })
                    EventEmitter.update_notification_count(user_key, unread_count)
                except Exception:
                    pass

                return True
            return False

        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return False

    @staticmethod
    def mark_all_read_and_emit(user_key: str, account_key: str) -> int:
        """Mark all notifications as read and emit update via WebSocket.

        Args:
            user_key: User key
            account_key: Account key

        Returns:
            Number of notifications marked as read
        """
        notification_repo = get_collection('notification')
        if not notification_repo:
            return 0

        try:
            result = notification_repo.update(
                {
                    'user_key': user_key,
                    'account_key': account_key,
                    'read': False
                },
                {
                    'read': True,
                    'read_at': get_time_date_dt(include_time=True),
                    'updated_at': get_time_date_dt(include_time=True)
                },
                multi=True
            )

            # Emit via WebSocket
            EventEmitter.emit_to_user(user_key, EventEmitter.NOTIFICATION_READ_ALL, {})
            EventEmitter.update_notification_count(user_key, 0)

            return result.modified_count if hasattr(result, 'modified_count') else 0

        except Exception as e:
            logger.error(f"Error marking all notifications as read: {e}")
            return 0

    @staticmethod
    def delete_and_emit(notification_id: str, user_key: str) -> bool:
        """Delete notification and emit update via WebSocket.

        Args:
            notification_id: Notification ID
            user_key: User key

        Returns:
            True if successful
        """
        notification_repo = get_collection('notification')
        if not notification_repo:
            return False

        try:
            result = notification_repo.delete({
                'notification_id': notification_id,
                'user_key': user_key
            })

            if result.deleted_count > 0:
                # Emit via WebSocket
                EventEmitter.emit_to_user(user_key, EventEmitter.NOTIFICATION_DELETED, {
                    'notification_id': notification_id
                })

                # Update unread count
                try:
                    unread_count = notification_repo.collection.count_documents({
                        'user_key': user_key,
                        'read': False
                    })
                    EventEmitter.update_notification_count(user_key, unread_count)
                except Exception:
                    pass

                return True
            return False

        except Exception as e:
            logger.error(f"Error deleting notification: {e}")
            return False

    @staticmethod
    def broadcast_and_emit(
        account_key: str,
        title: str,
        message: str,
        notification_type: str = 'info',
        priority: str = 'normal',
        data: Dict[str, Any] = None,
        created_by: str = None
    ) -> int:
        """Broadcast notification to all users in account and emit via WebSocket.

        Args:
            account_key: Account key
            title: Notification title
            message: Notification message
            notification_type: Type
            priority: Priority
            data: Additional data
            created_by: User who created the notification

        Returns:
            Number of notifications created
        """
        user_repo = get_collection('users')
        if not user_repo:
            return 0

        try:
            users = list(user_repo.find({'account_key': account_key}))
            count = 0

            for user in users:
                target_user_key = user.get('user_key')
                if target_user_key:
                    result = NotificationHandler.create_and_emit(
                        account_key=account_key,
                        target_user_key=target_user_key,
                        title=title,
                        message=message,
                        notification_type=notification_type,
                        priority=priority,
                        data={'broadcast': True, **(data or {})},
                        created_by=created_by
                    )
                    if result:
                        count += 1

            return count

        except Exception as e:
            logger.error(f"Error broadcasting notification: {e}")
            return 0

