"""Messaging service layer for business logic.

This service provides high-level messaging operations
and coordinates between the repository and real-time events.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fin_server.messaging.models import (
    Message, Conversation, MessageType, MessageStatus,
    ConversationType, PresenceStatus
)
from fin_server.messaging.repository import get_messaging_repository
from fin_server.utils.generator import generate_key

logger = logging.getLogger(__name__)


class MessagingService:
    """High-level messaging service."""

    def __init__(self):
        self.repo = get_messaging_repository()

    # =========================================================================
    # Conversation Operations
    # =========================================================================

    def get_or_create_direct_conversation(
        self,
        user_key: str,
        other_user_key: str,
        account_key: str
    ) -> Dict[str, Any]:
        """Get existing or create new direct conversation."""
        # Check if exists
        existing = self.repo.find_direct_conversation(user_key, other_user_key, account_key)
        if existing:
            return {
                'conversation_id': existing.get('conversation_id') or str(existing.get('_id')),
                'created': False,
                'conversation': existing
            }

        # Create new
        conversation = Conversation(
            conversation_id=f"CONV-{generate_key(10)}",
            conversation_type=ConversationType.DIRECT,
            participants=[user_key, other_user_key],
            created_by=user_key,
            account_key=account_key
        )

        conv_id = self.repo.create_conversation(conversation)
        conversation.conversation_id = conv_id

        return {
            'conversation_id': conv_id,
            'created': True,
            'conversation': conversation.to_dict()
        }

    def create_group_conversation(
        self,
        creator_key: str,
        account_key: str,
        name: str,
        participants: List[str],
        description: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new group conversation."""
        if creator_key not in participants:
            participants.append(creator_key)

        conversation = Conversation(
            conversation_id=f"GRP-{generate_key(10)}",
            conversation_type=ConversationType.GROUP,
            participants=participants,
            name=name,
            description=description,
            avatar_url=avatar_url,
            created_by=creator_key,
            admins=[creator_key],
            account_key=account_key
        )

        conv_id = self.repo.create_conversation(conversation)
        conversation.conversation_id = conv_id

        return {
            'conversation_id': conv_id,
            'conversation': conversation.to_dict()
        }

    def get_user_conversations_with_unread(
        self,
        user_key: str,
        account_key: str,
        include_archived: bool = False
    ) -> List[Dict[str, Any]]:
        """Get conversations with unread counts."""
        conversations = self.repo.get_user_conversations(
            user_key, account_key, include_archived
        )

        result = []
        for conv in conversations:
            conv_id = conv.get('conversation_id') or str(conv.get('_id'))
            conv_dict = dict(conv)
            conv_dict['_id'] = str(conv_dict.get('_id', ''))
            conv_dict['unreadCount'] = self.repo.get_unread_count(conv_id, user_key)

            # Check if muted/pinned/archived for this user
            conv_dict['isMuted'] = user_key in conv.get('muted_by', [])
            conv_dict['isPinned'] = user_key in conv.get('pinned_by', [])
            conv_dict['isArchived'] = user_key in conv.get('archived_by', [])

            result.append(conv_dict)

        # Sort: pinned first, then by last_activity
        result.sort(key=lambda x: (not x['isPinned'], x.get('last_activity') or datetime.min), reverse=True)

        return result

    # =========================================================================
    # Message Operations
    # =========================================================================

    def send_message(
        self,
        sender_key: str,
        conversation_id: str,
        content: str,
        account_key: str,
        message_type: str = MessageType.TEXT,
        reply_to: Optional[str] = None,
        media_url: Optional[str] = None,
        mentions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Send a message to a conversation."""
        # Verify sender is participant
        conv = self.repo.get_conversation(conversation_id, sender_key)
        if not conv:
            raise ValueError("Conversation not found or access denied")

        message = Message(
            message_id=f"MSG-{generate_key(12)}",
            conversation_id=conversation_id,
            sender_key=sender_key,
            content=content,
            message_type=message_type,
            reply_to=reply_to,
            media_url=media_url,
            mentions=mentions or [],
            account_key=account_key
        )

        message_id = self.repo.send_message(message)
        message.message_id = message_id

        return {
            'message_id': message_id,
            'message': message.to_dict(),
            'conversation': conv
        }

    def get_messages_paginated(
        self,
        conversation_id: str,
        user_key: str,
        before: Optional[str] = None,
        after: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get messages with pagination."""
        # Verify access
        conv = self.repo.get_conversation(conversation_id, user_key)
        if not conv:
            raise ValueError("Conversation not found or access denied")

        before_dt = datetime.fromisoformat(before) if before else None
        after_dt = datetime.fromisoformat(after) if after else None

        messages = self.repo.get_conversation_messages(
            conversation_id, before_dt, after_dt, limit
        )

        # Format messages
        formatted = []
        for msg in messages:
            msg_dict = dict(msg)
            msg_dict['_id'] = str(msg_dict.get('_id', ''))

            # Get read receipts for this message
            if msg.get('sender_key') == user_key:
                receipts = self.repo.get_message_receipts(
                    msg.get('message_id') or str(msg.get('_id'))
                )
                read_by = [r['user_key'] for r in receipts if r.get('status') == MessageStatus.READ]
                delivered_to = [r['user_key'] for r in receipts if r.get('status') in [MessageStatus.DELIVERED, MessageStatus.READ]]
                msg_dict['readBy'] = read_by
                msg_dict['deliveredTo'] = delivered_to

            formatted.append(msg_dict)

        return {
            'messages': formatted,
            'hasMore': len(messages) == limit,
            'conversation': conv
        }

    def forward_message(
        self,
        message_id: str,
        from_user_key: str,
        to_conversation_id: str,
        account_key: str
    ) -> Dict[str, Any]:
        """Forward a message to another conversation."""
        # Get original message
        original = self.repo.get_message(message_id)
        if not original:
            raise ValueError("Original message not found")

        # Create forwarded message
        message = Message(
            message_id=f"MSG-{generate_key(12)}",
            conversation_id=to_conversation_id,
            sender_key=from_user_key,
            content=original.get('content'),
            message_type=original.get('message_type', MessageType.TEXT),
            forwarded_from=message_id,
            media_url=original.get('media_url'),
            account_key=account_key
        )

        new_message_id = self.repo.send_message(message)
        message.message_id = new_message_id

        return {
            'message_id': new_message_id,
            'message': message.to_dict()
        }

    # =========================================================================
    # Search Operations
    # =========================================================================

    def search_messages(
        self,
        user_key: str,
        account_key: str,
        query: str,
        conversation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search messages by content."""
        messages = self.repo.search_messages(
            user_key, account_key, query, conversation_id
        )

        result = []
        for msg in messages:
            msg_dict = dict(msg)
            msg_dict['_id'] = str(msg_dict.get('_id', ''))
            result.append(msg_dict)

        return result

    def search_conversations(
        self,
        user_key: str,
        account_key: str,
        query: str
    ) -> List[Dict[str, Any]]:
        """Search conversations by name or participant."""
        conversations = self.repo.get_user_conversations(user_key, account_key)

        query_lower = query.lower()
        results = []

        for conv in conversations:
            name = conv.get('name', '') or ''
            participants = conv.get('participants', [])

            # Match by name or participant
            if query_lower in name.lower() or any(query_lower in p.lower() for p in participants):
                conv_dict = dict(conv)
                conv_dict['_id'] = str(conv_dict.get('_id', ''))
                results.append(conv_dict)

        return results

    # =========================================================================
    # Stats Operations
    # =========================================================================

    def get_unread_total(self, user_key: str, account_key: str) -> int:
        """Get total unread count across all conversations."""
        conversations = self.repo.get_user_conversations(user_key, account_key)
        total = 0
        for conv in conversations:
            conv_id = conv.get('conversation_id') or str(conv.get('_id'))
            total += self.repo.get_unread_count(conv_id, user_key)
        return total


# Singleton instance
_messaging_service = None

def get_messaging_service() -> MessagingService:
    """Get singleton messaging service instance."""
    global _messaging_service
    if _messaging_service is None:
        _messaging_service = MessagingService()
    return _messaging_service

