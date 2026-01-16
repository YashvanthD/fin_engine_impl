"""Chat message repository for chat feature.

Handles CRUD operations for chat messages.
Stored in media_db.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from bson import ObjectId

from fin_server.repository.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ChatMessageRepository(BaseRepository):
    """Repository for chat messages."""
    _instance = None

    def __new__(cls, db, collection_name="chat_messages"):
        if cls._instance is None:
            cls._instance = super(ChatMessageRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="chat_messages"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            self.coll = self.collection
            logger.info(f"Initializing {self.collection_name} collection in media_db")
            self._initialized = True

    def create_message(self, data: Dict[str, Any]) -> str:
        """Create a new message."""
        data['created_at'] = datetime.utcnow()
        data['status'] = data.get('status', 'sent')
        data['edited_at'] = None
        data['deleted_at'] = None
        data['deleted_for'] = []
        data['reactions'] = data.get('reactions', {})

        # Generate message_id if not provided
        if not data.get('message_id'):
            data['message_id'] = str(ObjectId())

        result = self.collection.insert_one(data)
        return data['message_id']

    def get_message(self, message_id: str) -> Optional[Dict]:
        """Get message by ID."""
        msg = self.collection.find_one({'message_id': message_id})
        if not msg:
            try:
                msg = self.collection.find_one({'_id': ObjectId(message_id)})
            except:
                msg = self.collection.find_one({'_id': message_id})
        return msg

    def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int = 50,
        before: datetime = None,
        after: datetime = None,
        user_key: str = None
    ) -> List[Dict]:
        """Get messages in a conversation with pagination."""
        query = {
            'conversation_id': conversation_id,
            'deleted_at': None
        }

        # Exclude messages deleted for this user
        if user_key:
            query['deleted_for'] = {'$ne': user_key}

        if before:
            query['created_at'] = {'$lt': before}
        elif after:
            query['created_at'] = {'$gt': after}

        # Sort newest first for loading older messages
        cursor = self.collection.find(query).sort('created_at', -1).limit(limit + 1)
        messages = list(cursor)

        return messages

    def edit_message(self, message_id: str, sender_key: str, new_content: str) -> bool:
        """Edit a message (only sender can edit)."""
        result = self.collection.update_one(
            {
                'message_id': message_id,
                'sender_key': sender_key,
                'deleted_at': None
            },
            {
                '$set': {
                    'content': new_content,
                    'edited_at': datetime.utcnow()
                },
                '$push': {
                    'edit_history': {
                        'content': new_content,
                        'edited_at': datetime.utcnow()
                    }
                }
            }
        )
        return result.modified_count > 0

    def delete_message(self, message_id: str, user_key: str, for_everyone: bool = False) -> bool:
        """Delete a message."""
        if for_everyone:
            # Only sender can delete for everyone
            result = self.collection.update_one(
                {
                    'message_id': message_id,
                    'sender_key': user_key,
                    'deleted_at': None
                },
                {'$set': {'deleted_at': datetime.utcnow()}}
            )
        else:
            # Delete only for this user
            result = self.collection.update_one(
                {'message_id': message_id},
                {'$addToSet': {'deleted_for': user_key}}
            )
        return result.modified_count > 0

    def add_reaction(self, message_id: str, user_key: str, emoji: str) -> bool:
        """Add reaction to a message."""
        result = self.collection.update_one(
            {'message_id': message_id},
            {'$addToSet': {f'reactions.{emoji}': user_key}}
        )
        return result.modified_count > 0

    def remove_reaction(self, message_id: str, user_key: str, emoji: str) -> bool:
        """Remove reaction from a message."""
        result = self.collection.update_one(
            {'message_id': message_id},
            {'$pull': {f'reactions.{emoji}': user_key}}
        )
        return result.modified_count > 0

    def search_messages(
        self,
        account_key: str,
        user_key: str,
        query_text: str,
        conversation_id: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """Search messages by text."""
        query = {
            'account_key': account_key,
            'deleted_at': None,
            'deleted_for': {'$ne': user_key},
            '$text': {'$search': query_text}
        }

        if conversation_id:
            query['conversation_id'] = conversation_id

        cursor = self.collection.find(
            query,
            {'score': {'$meta': 'textScore'}}
        ).sort([('score', {'$meta': 'textScore'})]).limit(limit)

        return list(cursor)

    def get_unread_count(self, conversation_id: str, user_key: str, last_read_at: datetime = None) -> int:
        """Get count of unread messages for a user in a conversation."""
        query = {
            'conversation_id': conversation_id,
            'sender_key': {'$ne': user_key},
            'deleted_at': None,
            'deleted_for': {'$ne': user_key}
        }

        if last_read_at:
            query['created_at'] = {'$gt': last_read_at}

        return self.collection.count_documents(query)

    def mark_messages_read(self, conversation_id: str, user_key: str, up_to_message_id: str = None) -> int:
        """Mark messages as read (for read receipts tracking)."""
        # This can be used with a separate read_receipts tracking
        # For now, we return count of messages that would be marked as read
        query = {
            'conversation_id': conversation_id,
            'sender_key': {'$ne': user_key},
            'deleted_at': None
        }

        if up_to_message_id:
            msg = self.get_message(up_to_message_id)
            if msg and msg.get('created_at'):
                query['created_at'] = {'$lte': msg['created_at']}

        return self.collection.count_documents(query)

