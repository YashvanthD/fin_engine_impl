"""User presence repository for chat feature.

Handles user online/offline status tracking.
Stored in media_db.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fin_server.repository.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class UserPresenceRepository(BaseRepository):
    """Repository for user presence status."""
    _instance = None

    def __new__(cls, db, collection_name="user_presence"):
        if cls._instance is None:
            cls._instance = super(UserPresenceRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="user_presence"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            self.coll = self.collection
            logger.info(f"Initializing {self.collection_name} collection in media_db")
            self._initialized = True

    def set_user_online(self, user_key: str, socket_id: str, device_info: Dict = None) -> bool:
        """Set user as online."""
        result = self.collection.update_one(
            {'user_key': user_key},
            {
                '$set': {
                    'status': 'online',
                    'socket_id': socket_id,
                    'device_info': device_info or {},
                    'last_seen': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                },
                '$setOnInsert': {
                    'created_at': datetime.utcnow()
                }
            },
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    def set_user_offline(self, user_key: str) -> bool:
        """Set user as offline."""
        result = self.collection.update_one(
            {'user_key': user_key},
            {
                '$set': {
                    'status': 'offline',
                    'socket_id': None,
                    'last_seen': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0

    def set_user_typing(self, user_key: str, conversation_id: str, is_typing: bool = True) -> bool:
        """Set user typing status."""
        if is_typing:
            result = self.collection.update_one(
                {'user_key': user_key},
                {
                    '$set': {
                        'status': 'typing',
                        'typing_in': conversation_id,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
        else:
            result = self.collection.update_one(
                {'user_key': user_key},
                {
                    '$set': {
                        'status': 'online',
                        'typing_in': None,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
        return result.modified_count > 0

    def get_user_presence(self, user_key: str) -> Optional[Dict]:
        """Get user presence status."""
        return self.collection.find_one({'user_key': user_key})

    def get_online_users(self, user_keys: List[str]) -> List[Dict]:
        """Get presence for multiple users."""
        return list(self.collection.find({
            'user_key': {'$in': user_keys},
            'status': {'$in': ['online', 'typing']}
        }))

    def is_user_online(self, user_key: str) -> bool:
        """Check if user is online."""
        presence = self.collection.find_one({'user_key': user_key})
        if presence:
            return presence.get('status') in ['online', 'typing']
        return False

    def get_all_online_users(self, account_key: str = None) -> List[Dict]:
        """Get all online users, optionally filtered by account."""
        query = {'status': {'$in': ['online', 'typing']}}
        if account_key:
            query['account_key'] = account_key
        return list(self.collection.find(query))

    def cleanup_stale_sessions(self, timeout_minutes: int = 30) -> int:
        """Mark stale sessions as offline."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)

        result = self.collection.update_many(
            {
                'status': {'$in': ['online', 'typing']},
                'updated_at': {'$lt': cutoff}
            },
            {
                '$set': {
                    'status': 'offline',
                    'socket_id': None,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        return result.modified_count

