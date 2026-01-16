"""Message receipt repository for chat feature.

Handles read/delivery receipts for messages.
Stored in media_db.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fin_server.repository.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class MessageReceiptRepository(BaseRepository):
    """Repository for message read/delivery receipts."""
    _instance = None

    def __new__(cls, db, collection_name="message_receipts"):
        if cls._instance is None:
            cls._instance = super(MessageReceiptRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="message_receipts"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            self.coll = self.collection
            logger.info(f"Initializing {self.collection_name} collection in media_db")
            self._initialized = True

    def mark_delivered(self, message_id: str, user_key: str) -> bool:
        """Mark message as delivered to user."""
        result = self.collection.update_one(
            {
                'message_id': message_id,
                'user_key': user_key
            },
            {
                '$set': {
                    'delivered_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                },
                '$setOnInsert': {
                    'created_at': datetime.utcnow()
                }
            },
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    def mark_read(self, message_id: str, user_key: str) -> bool:
        """Mark message as read by user."""
        result = self.collection.update_one(
            {
                'message_id': message_id,
                'user_key': user_key
            },
            {
                '$set': {
                    'read_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                },
                '$setOnInsert': {
                    'delivered_at': datetime.utcnow(),
                    'created_at': datetime.utcnow()
                }
            },
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    def mark_conversation_read(self, conversation_id: str, user_key: str, up_to_time: datetime = None) -> int:
        """Mark all messages in conversation as read."""
        if up_to_time is None:
            up_to_time = datetime.utcnow()

        result = self.collection.update_one(
            {
                'conversation_id': conversation_id,
                'user_key': user_key
            },
            {
                '$set': {
                    'last_read_at': up_to_time,
                    'updated_at': datetime.utcnow()
                },
                '$setOnInsert': {
                    'created_at': datetime.utcnow()
                }
            },
            upsert=True
        )
        return result.modified_count

    def get_message_receipts(self, message_id: str) -> List[Dict]:
        """Get all receipts for a message."""
        return list(self.collection.find({'message_id': message_id}))

    def get_read_status(self, message_id: str, user_key: str) -> Optional[Dict]:
        """Get read status for a specific user and message."""
        return self.collection.find_one({
            'message_id': message_id,
            'user_key': user_key
        })

    def get_conversation_last_read(self, conversation_id: str, user_key: str) -> Optional[datetime]:
        """Get last read timestamp for a user in a conversation."""
        receipt = self.collection.find_one({
            'conversation_id': conversation_id,
            'user_key': user_key
        })
        if receipt:
            return receipt.get('last_read_at')
        return None

    def get_unread_count(self, conversation_id: str, user_key: str, messages_collection) -> int:
        """Get count of unread messages for a user in a conversation."""
        last_read = self.get_conversation_last_read(conversation_id, user_key)

        query = {
            'conversation_id': conversation_id,
            'sender_key': {'$ne': user_key},
            'deleted_at': None,
            'deleted_for': {'$ne': user_key}
        }

        if last_read:
            query['created_at'] = {'$gt': last_read}

        return messages_collection.count_documents(query)

