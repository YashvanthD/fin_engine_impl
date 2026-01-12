"""Messaging repository for conversations and messages.

Provides CRUD operations for:
- Conversations (1-1, groups, broadcasts)
- Messages
- Read receipts
- User presence
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from bson import ObjectId

from fin_server.repository.mongo_helper import get_collection
from fin_server.messaging.models import (
    Message, Conversation, MessageReceipt, UserPresence,
    MessageType, MessageStatus, ConversationType, PresenceStatus
)

logger = logging.getLogger(__name__)


class MessagingRepository:
    """Repository for messaging operations."""

    def __init__(self):
        self.conversations = get_collection('conversations')
        self.messages = get_collection('messages')
        self.message_receipts = get_collection('message_receipts')
        self.user_presence = get_collection('user_presence')

    # =========================================================================
    # Conversation Operations
    # =========================================================================

    def create_conversation(self, conversation: Conversation) -> str:
        """Create a new conversation."""
        doc = conversation.to_db_doc()
        doc['created_at'] = datetime.utcnow()
        doc['last_activity'] = datetime.utcnow()

        # For direct conversations, check if one already exists
        if conversation.conversation_type == ConversationType.DIRECT:
            existing = self.find_direct_conversation(
                conversation.participants[0],
                conversation.participants[1] if len(conversation.participants) > 1 else None,
                conversation.account_key
            )
            if existing:
                return existing.get('conversation_id') or str(existing.get('_id'))

        result = self.conversations.insert_one(doc)
        return str(result.inserted_id)

    def find_direct_conversation(self, user1: str, user2: str, account_key: str) -> Optional[Dict]:
        """Find existing direct conversation between two users."""
        if not user2:
            return None
        return self.conversations.find_one({
            'conversation_type': ConversationType.DIRECT,
            'participants': {'$all': [user1, user2]},
            'account_key': account_key
        })

    def get_conversation(self, conversation_id: str, user_key: str = None) -> Optional[Dict]:
        """Get conversation by ID."""
        query = {'conversation_id': conversation_id}
        if user_key:
            query['participants'] = user_key
        conv = self.conversations.find_one(query)
        if not conv:
            # Try by _id
            try:
                conv = self.conversations.find_one({'_id': ObjectId(conversation_id)})
            except:
                conv = self.conversations.find_one({'_id': conversation_id})
        return conv

    def get_user_conversations(
        self,
        user_key: str,
        account_key: str,
        include_archived: bool = False,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict]:
        """Get all conversations for a user."""
        query = {
            'participants': user_key,
            'account_key': account_key
        }
        if not include_archived:
            query['archived_by'] = {'$ne': user_key}

        cursor = self.conversations.find(query).sort('last_activity', -1).skip(skip).limit(limit)
        return list(cursor)

    def add_participant(self, conversation_id: str, user_key: str, added_by: str) -> bool:
        """Add participant to group conversation."""
        result = self.conversations.update_one(
            {
                'conversation_id': conversation_id,
                'conversation_type': {'$in': [ConversationType.GROUP, ConversationType.BROADCAST]}
            },
            {
                '$addToSet': {'participants': user_key},
                '$set': {'last_activity': datetime.utcnow()}
            }
        )
        return result.modified_count > 0

    def remove_participant(self, conversation_id: str, user_key: str, removed_by: str) -> bool:
        """Remove participant from group conversation."""
        result = self.conversations.update_one(
            {'conversation_id': conversation_id},
            {
                '$pull': {'participants': user_key, 'admins': user_key},
                '$set': {'last_activity': datetime.utcnow()}
            }
        )
        return result.modified_count > 0

    def update_conversation(self, conversation_id: str, updates: Dict[str, Any]) -> bool:
        """Update conversation metadata."""
        allowed_fields = ['name', 'description', 'avatar_url', 'metadata']
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        filtered_updates['last_activity'] = datetime.utcnow()

        result = self.conversations.update_one(
            {'conversation_id': conversation_id},
            {'$set': filtered_updates}
        )
        return result.modified_count > 0

    def mute_conversation(self, conversation_id: str, user_key: str, mute: bool = True) -> bool:
        """Mute/unmute conversation for a user."""
        op = '$addToSet' if mute else '$pull'
        result = self.conversations.update_one(
            {'conversation_id': conversation_id},
            {op: {'muted_by': user_key}}
        )
        return result.modified_count > 0

    def pin_conversation(self, conversation_id: str, user_key: str, pin: bool = True) -> bool:
        """Pin/unpin conversation for a user."""
        op = '$addToSet' if pin else '$pull'
        result = self.conversations.update_one(
            {'conversation_id': conversation_id},
            {op: {'pinned_by': user_key}}
        )
        return result.modified_count > 0

    def archive_conversation(self, conversation_id: str, user_key: str, archive: bool = True) -> bool:
        """Archive/unarchive conversation for a user."""
        op = '$addToSet' if archive else '$pull'
        result = self.conversations.update_one(
            {'conversation_id': conversation_id},
            {op: {'archived_by': user_key}}
        )
        return result.modified_count > 0

    # =========================================================================
    # Message Operations
    # =========================================================================

    def send_message(self, message: Message) -> str:
        """Send a new message."""
        doc = message.to_db_doc()
        doc['created_at'] = datetime.utcnow()

        result = self.messages.insert_one(doc)
        message_id = str(result.inserted_id)

        # Update conversation last_message and last_activity
        self.conversations.update_one(
            {'conversation_id': message.conversation_id},
            {
                '$set': {
                    'last_message': {
                        'message_id': message_id,
                        'sender_key': message.sender_key,
                        'content': message.content[:100] if message.content else None,
                        'message_type': message.message_type,
                        'created_at': doc['created_at']
                    },
                    'last_activity': doc['created_at']
                }
            }
        )

        return message_id

    def get_message(self, message_id: str) -> Optional[Dict]:
        """Get message by ID."""
        msg = self.messages.find_one({'message_id': message_id})
        if not msg:
            try:
                msg = self.messages.find_one({'_id': ObjectId(message_id)})
            except:
                msg = self.messages.find_one({'_id': message_id})
        return msg

    def get_conversation_messages(
        self,
        conversation_id: str,
        before: Optional[datetime] = None,
        after: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get messages in a conversation with pagination."""
        query = {'conversation_id': conversation_id, 'deleted_at': None}

        if before:
            query['created_at'] = {'$lt': before}
        elif after:
            query['created_at'] = {'$gt': after}

        cursor = self.messages.find(query).sort('created_at', -1).limit(limit)
        messages = list(cursor)
        messages.reverse()  # Return in chronological order
        return messages

    def edit_message(self, message_id: str, sender_key: str, new_content: str) -> bool:
        """Edit a message (only by sender)."""
        result = self.messages.update_one(
            {'message_id': message_id, 'sender_key': sender_key, 'deleted_at': None},
            {
                '$set': {
                    'content': new_content,
                    'edited_at': datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0

    def delete_message(self, message_id: str, user_key: str, for_everyone: bool = False) -> bool:
        """Delete a message."""
        if for_everyone:
            # Only sender can delete for everyone
            result = self.messages.update_one(
                {'message_id': message_id, 'sender_key': user_key},
                {'$set': {'deleted_at': datetime.utcnow(), 'content': None}}
            )
        else:
            # Delete only for this user (add to deleted_for list)
            result = self.messages.update_one(
                {'message_id': message_id},
                {'$addToSet': {'deleted_for': user_key}}
            )
        return result.modified_count > 0

    def search_messages(
        self,
        user_key: str,
        account_key: str,
        query: str,
        conversation_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Search messages by content."""
        search_query = {
            'account_key': account_key,
            'content': {'$regex': query, '$options': 'i'},
            'deleted_at': None,
            'deleted_for': {'$ne': user_key}
        }

        if conversation_id:
            search_query['conversation_id'] = conversation_id

        cursor = self.messages.find(search_query).sort('created_at', -1).limit(limit)
        return list(cursor)

    # =========================================================================
    # Read Receipts
    # =========================================================================

    def mark_delivered(self, message_id: str, user_key: str) -> bool:
        """Mark message as delivered."""
        receipt = MessageReceipt(
            message_id=message_id,
            user_key=user_key,
            status=MessageStatus.DELIVERED
        )
        self.message_receipts.update_one(
            {'message_id': message_id, 'user_key': user_key},
            {'$set': receipt.to_db_doc()},
            upsert=True
        )
        return True

    def mark_read(self, message_id: str, user_key: str) -> bool:
        """Mark message as read."""
        receipt = MessageReceipt(
            message_id=message_id,
            user_key=user_key,
            status=MessageStatus.READ
        )
        self.message_receipts.update_one(
            {'message_id': message_id, 'user_key': user_key},
            {'$set': receipt.to_db_doc()},
            upsert=True
        )
        return True

    def mark_conversation_read(self, conversation_id: str, user_key: str) -> int:
        """Mark all messages in conversation as read."""
        # Get all unread messages in this conversation
        messages = self.messages.find({
            'conversation_id': conversation_id,
            'sender_key': {'$ne': user_key},
            'deleted_at': None
        })

        count = 0
        for msg in messages:
            msg_id = msg.get('message_id') or str(msg.get('_id'))
            self.mark_read(msg_id, user_key)
            count += 1

        return count

    def get_message_receipts(self, message_id: str) -> List[Dict]:
        """Get all receipts for a message."""
        return list(self.message_receipts.find({'message_id': message_id}))

    def get_unread_count(self, conversation_id: str, user_key: str) -> int:
        """Get unread message count for a conversation."""
        # Count messages not sent by user and not read by user
        total = self.messages.count_documents({
            'conversation_id': conversation_id,
            'sender_key': {'$ne': user_key},
            'deleted_at': None
        })

        read = self.message_receipts.count_documents({
            'conversation_id': conversation_id,
            'user_key': user_key,
            'status': MessageStatus.READ
        })

        return max(0, total - read)

    # =========================================================================
    # User Presence
    # =========================================================================

    def set_user_online(self, user_key: str, socket_id: str, device_info: Dict = None) -> bool:
        """Set user as online."""
        presence = UserPresence(
            user_key=user_key,
            status=PresenceStatus.ONLINE,
            socket_id=socket_id,
            device_info=device_info or {}
        )
        self.user_presence.update_one(
            {'user_key': user_key},
            {'$set': presence.to_db_doc()},
            upsert=True
        )
        return True

    def set_user_offline(self, user_key: str) -> bool:
        """Set user as offline."""
        self.user_presence.update_one(
            {'user_key': user_key},
            {
                '$set': {
                    'status': PresenceStatus.OFFLINE,
                    'last_seen': datetime.utcnow(),
                    'socket_id': None
                }
            }
        )
        return True

    def set_user_typing(self, user_key: str, conversation_id: str, is_typing: bool = True) -> bool:
        """Set user typing status."""
        status = PresenceStatus.TYPING if is_typing else PresenceStatus.ONLINE
        self.user_presence.update_one(
            {'user_key': user_key},
            {
                '$set': {
                    'status': status,
                    'typing_in': conversation_id if is_typing else None
                }
            }
        )
        return True

    def get_user_presence(self, user_key: str) -> Optional[Dict]:
        """Get user presence status."""
        return self.user_presence.find_one({'user_key': user_key})

    def get_online_users(self, user_keys: List[str]) -> List[Dict]:
        """Get presence for multiple users."""
        return list(self.user_presence.find({
            'user_key': {'$in': user_keys},
            'status': {'$in': [PresenceStatus.ONLINE, PresenceStatus.TYPING]}
        }))


# Singleton instance
_messaging_repo = None

def get_messaging_repository() -> MessagingRepository:
    """Get singleton messaging repository instance."""
    global _messaging_repo
    if _messaging_repo is None:
        _messaging_repo = MessagingRepository()
    return _messaging_repo

