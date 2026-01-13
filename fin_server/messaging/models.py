"""Messaging data models for WhatsApp/Telegram-like chat functionality.

Collections:
- conversations: Chat conversations (1-1 or group)
- messages: Individual messages
- message_status: Read receipts and delivery status
- user_presence: Online/offline status
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"
    LOCATION = "location"
    NOTIFICATION = "notification"
    SYSTEM = "system"


class MessageStatus(str, Enum):
    SENT = "sent"          # Message sent to server
    DELIVERED = "delivered" # Message delivered to recipient device
    READ = "read"          # Message read by recipient
    FAILED = "failed"      # Message failed to send


class ConversationType(str, Enum):
    DIRECT = "direct"      # 1-1 conversation
    GROUP = "group"        # Group chat
    BROADCAST = "broadcast" # Broadcast list (one-way)


class PresenceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    AWAY = "away"
    TYPING = "typing"


class Message:
    """Message document structure."""

    def __init__(
        self,
        message_id: str,
        conversation_id: str,
        sender_key: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        reply_to: Optional[str] = None,
        forwarded_from: Optional[str] = None,
        media_url: Optional[str] = None,
        media_thumbnail: Optional[str] = None,
        mentions: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        edited_at: Optional[datetime] = None,
        deleted_at: Optional[datetime] = None,
        account_key: Optional[str] = None,
        sender_info: Optional[Dict[str, Any]] = None  # Denormalized sender info
    ):
        self.message_id = message_id
        self.conversation_id = conversation_id
        self.sender_key = sender_key
        self.content = content
        self.message_type = message_type
        self.reply_to = reply_to
        self.forwarded_from = forwarded_from
        self.media_url = media_url
        self.media_thumbnail = media_thumbnail
        self.mentions = mentions or []
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.edited_at = edited_at
        self.deleted_at = deleted_at
        self.account_key = account_key
        # Denormalized sender info for faster reads
        self.sender_info = sender_info  # {user_key, username, avatar_url}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'messageId': self.message_id,
            'conversationId': self.conversation_id,
            'senderKey': self.sender_key,
            'senderInfo': self.sender_info,  # Include denormalized sender info
            'content': self.content if not self.deleted_at else None,
            'messageType': self.message_type,
            'replyTo': self.reply_to,
            'forwardedFrom': self.forwarded_from,
            'mediaUrl': self.media_url,
            'mediaThumbnail': self.media_thumbnail,
            'mentions': self.mentions,
            'metadata': self.metadata,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'editedAt': self.edited_at.isoformat() if self.edited_at else None,
            'isDeleted': bool(self.deleted_at),
            'accountKey': self.account_key
        }

    def to_db_doc(self) -> Dict[str, Any]:
        return {
            '_id': self.message_id,
            'message_id': self.message_id,
            'conversation_id': self.conversation_id,
            'sender_key': self.sender_key,
            'sender_info': self.sender_info,  # Store denormalized sender info
            'content': self.content,
            'message_type': self.message_type,
            'reply_to': self.reply_to,
            'forwarded_from': self.forwarded_from,
            'media_url': self.media_url,
            'media_thumbnail': self.media_thumbnail,
            'mentions': self.mentions,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'edited_at': self.edited_at,
            'deleted_at': self.deleted_at,
            'account_key': self.account_key
        }

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> 'Message':
        return cls(
            message_id=doc.get('message_id') or str(doc.get('_id')),
            conversation_id=doc.get('conversation_id'),
            sender_key=doc.get('sender_key'),
            content=doc.get('content'),
            message_type=doc.get('message_type', MessageType.TEXT),
            reply_to=doc.get('reply_to'),
            forwarded_from=doc.get('forwarded_from'),
            media_url=doc.get('media_url'),
            media_thumbnail=doc.get('media_thumbnail'),
            mentions=doc.get('mentions', []),
            metadata=doc.get('metadata', {}),
            created_at=doc.get('created_at'),
            edited_at=doc.get('edited_at'),
            deleted_at=doc.get('deleted_at'),
            account_key=doc.get('account_key'),
            sender_info=doc.get('sender_info')
        )


class Conversation:
    """Conversation document structure."""

    def __init__(
        self,
        conversation_id: str,
        conversation_type: ConversationType,
        participants: List[str],
        name: Optional[str] = None,
        description: Optional[str] = None,
        avatar_url: Optional[str] = None,
        created_by: Optional[str] = None,
        admins: Optional[List[str]] = None,
        last_message: Optional[Dict[str, Any]] = None,
        last_activity: Optional[datetime] = None,
        muted_by: Optional[List[str]] = None,
        pinned_by: Optional[List[str]] = None,
        archived_by: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        account_key: Optional[str] = None,
        unread_counts: Optional[Dict[str, int]] = None  # {user_key: count}
    ):
        self.conversation_id = conversation_id
        self.conversation_type = conversation_type
        self.participants = participants
        self.name = name
        self.description = description
        self.avatar_url = avatar_url
        self.created_by = created_by
        self.admins = admins or []
        self.last_message = last_message
        self.last_activity = last_activity or datetime.utcnow()
        self.muted_by = muted_by or []
        self.pinned_by = pinned_by or []
        self.archived_by = archived_by or []
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.account_key = account_key
        # Denormalized unread counts per user {user_key: count}
        self.unread_counts = unread_counts or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'conversationId': self.conversation_id,
            'conversationType': self.conversation_type,
            'participants': self.participants,
            'name': self.name,
            'description': self.description,
            'avatarUrl': self.avatar_url,
            'createdBy': self.created_by,
            'admins': self.admins,
            'lastMessage': self.last_message,
            'lastActivity': self.last_activity.isoformat() if self.last_activity else None,
            'metadata': self.metadata,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'accountKey': self.account_key,
            'unreadCounts': self.unread_counts
        }

    def to_db_doc(self) -> Dict[str, Any]:
        return {
            '_id': self.conversation_id,
            'conversation_id': self.conversation_id,
            'conversation_type': self.conversation_type,
            'participants': self.participants,
            'name': self.name,
            'description': self.description,
            'avatar_url': self.avatar_url,
            'created_by': self.created_by,
            'admins': self.admins,
            'last_message': self.last_message,
            'last_activity': self.last_activity,
            'muted_by': self.muted_by,
            'pinned_by': self.pinned_by,
            'archived_by': self.archived_by,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'account_key': self.account_key,
            'unread_counts': self.unread_counts
        }

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> 'Conversation':
        return cls(
            conversation_id=doc.get('conversation_id') or str(doc.get('_id')),
            conversation_type=doc.get('conversation_type', ConversationType.DIRECT),
            participants=doc.get('participants', []),
            name=doc.get('name'),
            description=doc.get('description'),
            avatar_url=doc.get('avatar_url'),
            created_by=doc.get('created_by'),
            admins=doc.get('admins', []),
            last_message=doc.get('last_message'),
            last_activity=doc.get('last_activity'),
            muted_by=doc.get('muted_by', []),
            pinned_by=doc.get('pinned_by', []),
            archived_by=doc.get('archived_by', []),
            metadata=doc.get('metadata', {}),
            created_at=doc.get('created_at'),
            account_key=doc.get('account_key'),
            unread_counts=doc.get('unread_counts', {})
        )


class MessageReceipt:
    """Message read/delivery receipt."""

    def __init__(
        self,
        message_id: str,
        user_key: str,
        status: MessageStatus,
        timestamp: Optional[datetime] = None
    ):
        self.message_id = message_id
        self.user_key = user_key
        self.status = status
        self.timestamp = timestamp or datetime.utcnow()

    def to_db_doc(self) -> Dict[str, Any]:
        return {
            'message_id': self.message_id,
            'user_key': self.user_key,
            'status': self.status,
            'timestamp': self.timestamp
        }


class UserPresence:
    """User online/offline status."""

    def __init__(
        self,
        user_key: str,
        status: PresenceStatus,
        last_seen: Optional[datetime] = None,
        socket_id: Optional[str] = None,
        device_info: Optional[Dict[str, Any]] = None
    ):
        self.user_key = user_key
        self.status = status
        self.last_seen = last_seen or datetime.utcnow()
        self.socket_id = socket_id
        self.device_info = device_info or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'userKey': self.user_key,
            'status': self.status,
            'lastSeen': self.last_seen.isoformat() if self.last_seen else None
        }

    def to_db_doc(self) -> Dict[str, Any]:
        return {
            '_id': self.user_key,
            'user_key': self.user_key,
            'status': self.status,
            'last_seen': self.last_seen,
            'socket_id': self.socket_id,
            'device_info': self.device_info
        }

