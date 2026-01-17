"""User Conversations Repository.

Maps user_key to their conversation IDs for fast lookup.
Stored in media_db.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fin_server.repository.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class UserConversationsRepository(BaseRepository):
    """Repository for user_conversations - fast lookup of user's conversations."""
    _instance = None

    def __new__(cls, db, collection_name="user_conversations"):
        if cls._instance is None:
            cls._instance = super(UserConversationsRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="user_conversations"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            self.coll = self.collection
            logger.info(f"Initializing {self.collection_name} collection in media_db")
            self._ensure_indexes()
            self._initialized = True

    def _ensure_indexes(self):
        """Create necessary indexes."""
        if self.collection is not None:
            try:
                self.collection.create_index("user_key", unique=True)
                logger.info(f"Created index on {self.collection_name}.user_key")
            except Exception as e:
                logger.warning(f"Could not create index: {e}")

    def get_user_doc(self, user_key: str) -> Optional[Dict]:
        """Get the user_conversations document for a user."""
        if self.collection is None:
            return None
        return self.collection.find_one({'user_key': user_key})

    def get_conversation_ids(self, user_key: str) -> List[str]:
        """Get list of conversation IDs for a user."""
        doc = self.get_user_doc(user_key)
        if not doc:
            return []
        return [c.get('conversation_id') for c in doc.get('conversations', []) if c.get('conversation_id')]

    def add_conversation(self, user_key: str, conversation_id: str) -> bool:
        """Add a conversation to user's list."""
        if self.collection is None:
            return False

        now = datetime.utcnow()
        conv_entry = {
            'conversation_id': conversation_id,
            'joined_at': now,
            'is_muted': False,
            'is_pinned': False,
            'is_archived': False,
            'last_read_at': None,
            'unread_count': 0
        }

        result = self.collection.update_one(
            {'user_key': user_key},
            {
                '$setOnInsert': {'user_key': user_key, 'created_at': now},
                '$push': {'conversations': conv_entry},
                '$set': {'updated_at': now}
            },
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    def remove_conversation(self, user_key: str, conversation_id: str) -> bool:
        """Remove a conversation from user's list."""
        if self.collection is None:
            return False

        result = self.collection.update_one(
            {'user_key': user_key},
            {
                '$pull': {'conversations': {'conversation_id': conversation_id}},
                '$set': {'updated_at': datetime.utcnow()}
            }
        )
        return result.modified_count > 0

    def update_unread_count(self, user_key: str, conversation_id: str, count: int) -> bool:
        """Update unread count for a conversation."""
        if self.collection is None:
            return False

        result = self.collection.update_one(
            {'user_key': user_key, 'conversations.conversation_id': conversation_id},
            {
                '$set': {
                    'conversations.$.unread_count': count,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0

    def increment_unread(self, user_key: str, conversation_id: str) -> bool:
        """Increment unread count by 1."""
        if self.collection is None:
            return False

        result = self.collection.update_one(
            {'user_key': user_key, 'conversations.conversation_id': conversation_id},
            {
                '$inc': {'conversations.$.unread_count': 1},
                '$set': {'updated_at': datetime.utcnow()}
            }
        )
        return result.modified_count > 0

    def mark_read(self, user_key: str, conversation_id: str) -> bool:
        """Mark conversation as read (reset unread to 0)."""
        if self.collection is None:
            return False

        result = self.collection.update_one(
            {'user_key': user_key, 'conversations.conversation_id': conversation_id},
            {
                '$set': {
                    'conversations.$.unread_count': 0,
                    'conversations.$.last_read_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0

    def set_muted(self, user_key: str, conversation_id: str, is_muted: bool) -> bool:
        """Set mute status for a conversation."""
        if self.collection is None:
            return False

        result = self.collection.update_one(
            {'user_key': user_key, 'conversations.conversation_id': conversation_id},
            {
                '$set': {
                    'conversations.$.is_muted': is_muted,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0

    def set_pinned(self, user_key: str, conversation_id: str, is_pinned: bool) -> bool:
        """Set pinned status for a conversation."""
        if self.collection is None:
            return False

        result = self.collection.update_one(
            {'user_key': user_key, 'conversations.conversation_id': conversation_id},
            {
                '$set': {
                    'conversations.$.is_pinned': is_pinned,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0

    def set_archived(self, user_key: str, conversation_id: str, is_archived: bool) -> bool:
        """Set archived status for a conversation."""
        if self.collection is None:
            return False

        result = self.collection.update_one(
            {'user_key': user_key, 'conversations.conversation_id': conversation_id},
            {
                '$set': {
                    'conversations.$.is_archived': is_archived,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0

    def get_total_unread(self, user_key: str) -> int:
        """Get total unread count across all conversations."""
        doc = self.get_user_doc(user_key)
        if not doc:
            return 0
        return sum(c.get('unread_count', 0) for c in doc.get('conversations', []))

