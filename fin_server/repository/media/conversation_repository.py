"""Conversation repository for chat feature.

Handles CRUD operations for chat conversations (direct, group, broadcast).
Stored in media_db.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from bson import ObjectId

from fin_server.repository.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ConversationRepository(BaseRepository):
    """Repository for chat conversations."""
    _instance = None

    def __new__(cls, db, collection_name="conversations"):
        if cls._instance is None:
            cls._instance = super(ConversationRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="conversations"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            self.coll = self.collection
            logger.info(f"Initializing {self.collection_name} collection in media_db")
            self._initialized = True

    def create_conversation(self, data: Dict[str, Any]) -> str:
        """Create a new conversation."""
        data['created_at'] = datetime.utcnow()
        data['last_activity'] = datetime.utcnow()

        # For direct conversations, check if one already exists
        if data.get('conversation_type') == 'direct':
            participants = data.get('participants', [])
            if len(participants) >= 2:
                existing = self.find_direct_conversation(
                    participants[0],
                    participants[1],
                    data.get('account_key')
                )
                if existing:
                    return existing.get('conversation_id') or str(existing.get('_id'))

        result = self.collection.insert_one(data)
        return str(result.inserted_id)

    def find_direct_conversation(self, user1: str, user2: str, account_key: str) -> Optional[Dict]:
        """Find existing direct conversation between two users."""
        if not user2:
            return None
        return self.collection.find_one({
            'conversation_type': 'direct',
            'participants': {'$all': [user1, user2]},
            'account_key': account_key
        })

    def get_conversation(self, conversation_id: str, user_key: str = None) -> Optional[Dict]:
        """Get conversation by ID."""
        query = {'conversation_id': conversation_id}
        if user_key:
            query['participants'] = user_key
        conv = self.collection.find_one(query)
        if not conv:
            # Try by _id
            try:
                conv = self.collection.find_one({'_id': ObjectId(conversation_id)})
            except:
                conv = self.collection.find_one({'_id': conversation_id})
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

        cursor = self.collection.find(query).sort('last_activity', -1).skip(skip).limit(limit)
        return list(cursor)

    def add_participant(self, conversation_id: str, user_key: str) -> bool:
        """Add participant to group conversation."""
        result = self.collection.update_one(
            {
                'conversation_id': conversation_id,
                'conversation_type': {'$in': ['group', 'broadcast']}
            },
            {
                '$addToSet': {'participants': user_key},
                '$set': {'last_activity': datetime.utcnow()}
            }
        )
        return result.modified_count > 0

    def remove_participant(self, conversation_id: str, user_key: str) -> bool:
        """Remove participant from group conversation."""
        result = self.collection.update_one(
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

        result = self.collection.update_one(
            {'conversation_id': conversation_id},
            {'$set': filtered_updates}
        )
        return result.modified_count > 0

    def mute_conversation(self, conversation_id: str, user_key: str, mute: bool = True) -> bool:
        """Mute/unmute conversation for a user."""
        op = '$addToSet' if mute else '$pull'
        result = self.collection.update_one(
            {'conversation_id': conversation_id},
            {op: {'muted_by': user_key}}
        )
        return result.modified_count > 0

    def pin_conversation(self, conversation_id: str, user_key: str, pin: bool = True) -> bool:
        """Pin/unpin conversation for a user."""
        op = '$addToSet' if pin else '$pull'
        result = self.collection.update_one(
            {'conversation_id': conversation_id},
            {op: {'pinned_by': user_key}}
        )
        return result.modified_count > 0

    def archive_conversation(self, conversation_id: str, user_key: str, archive: bool = True) -> bool:
        """Archive/unarchive conversation for a user."""
        op = '$addToSet' if archive else '$pull'
        result = self.collection.update_one(
            {'conversation_id': conversation_id},
            {op: {'archived_by': user_key}}
        )
        return result.modified_count > 0

    def update_last_activity(self, conversation_id: str) -> bool:
        """Update last activity timestamp."""
        result = self.collection.update_one(
            {'conversation_id': conversation_id},
            {'$set': {'last_activity': datetime.utcnow()}}
        )
        return result.modified_count > 0

