"""Messaging module with WhatsApp/Telegram-like features.

This module provides:
- Real-time messaging via Socket.IO
- Direct and group conversations
- Read receipts and typing indicators
- User presence (online/offline)
- Message search and forwarding
"""

from fin_server.messaging.models import (
    Message, Conversation, MessageReceipt, UserPresence,
    MessageType, MessageStatus, ConversationType, PresenceStatus
)
from fin_server.messaging.repository import (
    MessagingRepository, get_messaging_repository
)
from fin_server.messaging.service import (
    MessagingService, get_messaging_service
)
from fin_server.messaging.socket_server import (
    socketio, start_notification_worker
)

__all__ = [
    # Models
    'Message', 'Conversation', 'MessageReceipt', 'UserPresence',
    'MessageType', 'MessageStatus', 'ConversationType', 'PresenceStatus',
    # Repository
    'MessagingRepository', 'get_messaging_repository',
    # Service
    'MessagingService', 'get_messaging_service',
    # Socket
    'socketio', 'start_notification_worker'
]
