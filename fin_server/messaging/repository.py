"""Messaging repository for conversations and messages.

Provides CRUD operations for:
- Conversations (1-1, groups, broadcasts)
- Messages
- Read receipts
- User presence

This is a facade that delegates to the proper repositories in media folder.
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
    """Repository facade for messaging operations.

    Delegates to proper repository classes:
    - ConversationRepository for conversations
    - ChatMessageRepository for chat_messages
    - MessageReceiptRepository for message_receipts
    - UserPresenceRepository for user_presence

    Uses lazy initialization to handle cases where MongoDB is not yet connected.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MessagingRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, '_initialized', False):
            return

        # Initialize repo references as None - will be lazily loaded
        self._conversations_repo = None
        self._messages_repo = None
        self._receipts_repo = None
        self._presence_repo = None
        self._user_conversations_repo = None
        self._collections_initialized = False
        self._initialized = True
        logger.info("MessagingRepository initialized (lazy loading enabled)")

    def _ensure_collections(self):
        """Lazily initialize collection references."""
        if self._collections_initialized:
            return

        # Get the repository instances from MongoRepo
        self._conversations_repo = get_collection('conversations')
        self._messages_repo = get_collection('chat_messages')
        self._receipts_repo = get_collection('message_receipts')
        self._presence_repo = get_collection('user_presence')
        self._user_conversations_repo = get_collection('user_conversations')

        # Log initialization status
        if self._conversations_repo is None:
            logger.warning("MessagingRepository: 'conversations' repository is None - chat features unavailable")
        else:
            logger.info("MessagingRepository: 'conversations' repository initialized")
        if self._messages_repo is None:
            logger.warning("MessagingRepository: 'chat_messages' repository is None - chat features unavailable")
        else:
            logger.info("MessagingRepository: 'chat_messages' repository initialized")
        if self._receipts_repo is None:
            logger.warning("MessagingRepository: 'message_receipts' repository is None")
        if self._presence_repo is None:
            logger.warning("MessagingRepository: 'user_presence' repository is None")
        if self._user_conversations_repo is None:
            logger.warning("MessagingRepository: 'user_conversations' repository is None")
        else:
            logger.info("MessagingRepository: 'user_conversations' repository initialized")

        self._collections_initialized = True

    @property
    def conversations(self):
        """Get conversations collection (lazy load)."""
        self._ensure_collections()
        if self._conversations_repo is None:
            return None
        return getattr(self._conversations_repo, 'collection', None)

    @property
    def messages(self):
        """Get messages collection (lazy load)."""
        self._ensure_collections()
        if self._messages_repo is None:
            return None
        return getattr(self._messages_repo, 'collection', None)

    @property
    def message_receipts(self):
        """Get message receipts collection (lazy load)."""
        self._ensure_collections()
        if self._receipts_repo is None:
            return None
        return getattr(self._receipts_repo, 'collection', None)

    @property
    def user_presence(self):
        """Get user presence collection (lazy load)."""
        self._ensure_collections()
        if self._presence_repo is None:
            return None
        return getattr(self._presence_repo, 'collection', None)

    @property
    def user_conversations(self):
        """Get user_conversations collection (lazy load)."""
        self._ensure_collections()
        if self._user_conversations_repo is None:
            return None
        return getattr(self._user_conversations_repo, 'collection', None)

    def is_available(self) -> bool:
        """Check if messaging repository is properly initialized."""
        self._ensure_collections()
        return self._conversations_repo is not None and self._messages_repo is not None

    # =========================================================================
    # Conversation Operations
    # =========================================================================

    def create_conversation(self, conversation: Conversation) -> str:
        """Create a new conversation."""
        if self.conversations is None:
            raise RuntimeError("Conversations collection not available - MongoDB may not be connected")

        doc = conversation.to_db_doc()
        doc['created_at'] = datetime.utcnow()
        doc['last_activity'] = datetime.utcnow()

        print(f"REPO: Creating conversation: {conversation.conversation_id}")
        print(f"REPO: Participants: {conversation.participants}")
        print(f"REPO: Participants type: {type(conversation.participants)}")
        print(f"REPO: Account key: {conversation.account_key}")
        print(f"REPO: Doc to insert: {doc}")

        # For direct conversations, check if one already exists
        if conversation.conversation_type == ConversationType.DIRECT:
            existing = self.find_direct_conversation(
                conversation.participants[0],
                conversation.participants[1] if len(conversation.participants) > 1 else None,
                conversation.account_key
            )
            if existing:
                existing_id = existing.get('conversation_id') or str(existing.get('_id'))
                print(f"REPO: Existing direct conversation found: {existing_id}")
                return existing_id

        result = self.conversations.insert_one(doc)
        conv_id = conversation.conversation_id
        print(f"REPO: Conversation created successfully: {conv_id} (MongoDB _id: {result.inserted_id})")

        # Add conversation to each participant's user_conversations
        self._add_conversation_to_users(conv_id, conversation.participants)

        return conv_id

    def _add_conversation_to_users(self, conversation_id: str, participants: list):
        """Add conversation to each participant's user_conversations collection."""
        if self.user_conversations is None:
            print("REPO: user_conversations collection not available, skipping")
            return

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

        for user_key in participants:
            try:
                # Upsert: create user doc if not exists, add conversation to array
                self.user_conversations.update_one(
                    {'user_key': user_key},
                    {
                        '$setOnInsert': {'user_key': user_key, 'created_at': now},
                        '$push': {'conversations': conv_entry},
                        '$set': {'updated_at': now}
                    },
                    upsert=True
                )
                print(f"REPO: Added conversation {conversation_id} to user {user_key}")
            except Exception as e:
                print(f"REPO: ERROR adding conversation to user {user_key}: {e}")

    def find_direct_conversation(self, user1: str, user2: str, account_key: str) -> Optional[Dict]:
        """Find existing direct conversation between two users."""
        if not user2:
            return None
        if self.conversations is None:
            logger.error("Conversations collection not available")
            return None
        return self.conversations.find_one({
            'conversation_type': ConversationType.DIRECT,
            'participants': {'$all': [user1, user2]},
            'account_key': account_key
        })

    def get_conversation(self, conversation_id: str, user_key: str = None) -> Optional[Dict]:
        """Get conversation by ID."""
        if self.conversations is None:
            print("REPO: ERROR - Conversations collection not available")
            return None

        print(f"REPO: get_conversation - conversation_id={conversation_id}, user_key={user_key}")

        # First try to find by conversation_id only
        conv = self.conversations.find_one({'conversation_id': conversation_id})

        if not conv:
            print(f"REPO: Not found by conversation_id, trying by _id...")
            # Try by _id
            try:
                from bson import ObjectId
                conv = self.conversations.find_one({'_id': ObjectId(conversation_id)})
            except:
                conv = self.conversations.find_one({'_id': conversation_id})

        if conv:
            print(f"REPO: Found conversation: {conv.get('conversation_id', conv.get('_id'))}")
            print(f"REPO: Participants: {conv.get('participants')}")
            print(f"REPO: Participants type: {type(conv.get('participants'))}")

            # Check if user is a participant
            if user_key:
                participants = conv.get('participants', [])
                print(f"REPO: Checking if user_key '{user_key}' is in participants: {participants}")

                # Handle both string and list participants
                if isinstance(participants, list):
                    is_participant = user_key in participants
                else:
                    is_participant = user_key == participants

                print(f"REPO: Is participant: {is_participant}")

                if not is_participant:
                    print(f"REPO: WARNING - User {user_key} is NOT a participant in conversation {conversation_id}")
                    return None
        else:
            print(f"REPO: Conversation not found: {conversation_id}")
            # Debug: list all conversations
            all_convs = list(self.conversations.find({}).limit(10))
            print(f"REPO: Total conversations in DB (first 10):")
            for c in all_convs:
                print(f"REPO:   - ID: {c.get('conversation_id', c.get('_id'))}, participants: {c.get('participants')}")

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
        if self.conversations is None:
            logger.error("Conversations collection not available")
            return []

        query = {
            'participants': user_key,
            'account_key': account_key
        }
        if not include_archived:
            query['archived_by'] = {'$ne': user_key}

        cursor = self.conversations.find(query).sort('last_activity', -1).skip(skip).limit(limit)
        return list(cursor)

    def get_user_conversation_ids(self, user_key: str) -> List[str]:
        """Get list of conversation IDs for a user (fast lookup from user_conversations).

        Returns:
            List of conversation_id strings
        """
        if self.user_conversations is None:
            print(f"REPO: user_conversations collection not available, falling back to conversations")
            # Fallback to querying conversations collection
            if self.conversations is None:
                return []
            cursor = self.conversations.find(
                {'participants': user_key},
                {'conversation_id': 1}
            )
            return [c.get('conversation_id') or str(c.get('_id')) for c in cursor]

        doc = self.user_conversations.find_one({'user_key': user_key})
        if not doc:
            return []

        conversations = doc.get('conversations', [])
        return [c.get('conversation_id') for c in conversations if c.get('conversation_id')]

    def get_user_conversations_summary(self, user_key: str) -> Dict:
        """Get user's conversation summary (for initial load).

        Returns:
            {
                'user_key': '...',
                'conversations': [
                    {
                        'conversation_id': 'conv_123',
                        'is_muted': False,
                        'is_pinned': True,
                        'unread_count': 5,
                        ...
                    }
                ],
                'total_unread': 10
            }
        """
        if self.user_conversations is None:
            return {'user_key': user_key, 'conversations': [], 'total_unread': 0}

        doc = self.user_conversations.find_one({'user_key': user_key})
        if not doc:
            return {'user_key': user_key, 'conversations': [], 'total_unread': 0}

        conversations = doc.get('conversations', [])
        total_unread = sum(c.get('unread_count', 0) for c in conversations)

        return {
            'user_key': user_key,
            'conversations': conversations,
            'total_unread': total_unread
        }

    def update_user_conversation_unread(self, user_key: str, conversation_id: str, unread_count: int):
        """Update unread count for a user's conversation."""
        if self.user_conversations is None:
            return

        self.user_conversations.update_one(
            {'user_key': user_key, 'conversations.conversation_id': conversation_id},
            {
                '$set': {
                    'conversations.$.unread_count': unread_count,
                    'updated_at': datetime.utcnow()
                }
            }
        )

    def increment_user_conversation_unread(self, user_key: str, conversation_id: str):
        """Increment unread count for a user's conversation."""
        if self.user_conversations is None:
            return

        self.user_conversations.update_one(
            {'user_key': user_key, 'conversations.conversation_id': conversation_id},
            {
                '$inc': {'conversations.$.unread_count': 1},
                '$set': {'updated_at': datetime.utcnow()}
            }
        )

    def mark_user_conversation_read(self, user_key: str, conversation_id: str):
        """Mark a conversation as read (reset unread count)."""
        if self.user_conversations is None:
            return

        self.user_conversations.update_one(
            {'user_key': user_key, 'conversations.conversation_id': conversation_id},
            {
                '$set': {
                    'conversations.$.unread_count': 0,
                    'conversations.$.last_read_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                }
            }
        )

    def add_participant(self, conversation_id: str, user_key: str, added_by: str) -> bool:
        """Add participant to group conversation."""
        if self.conversations is None:
            logger.error("Conversations collection not available")
            return False
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

        if result.modified_count > 0:
            # Also add to user_conversations
            self._add_conversation_to_users(conversation_id, [user_key])

        return result.modified_count > 0

    def remove_participant(self, conversation_id: str, user_key: str, removed_by: str) -> bool:
        """Remove participant from group conversation."""
        if self.conversations is None:
            logger.error("Conversations collection not available")
            return False
        result = self.conversations.update_one(
            {'conversation_id': conversation_id},
            {
                '$pull': {'participants': user_key, 'admins': user_key},
                '$set': {'last_activity': datetime.utcnow()}
            }
        )

        if result.modified_count > 0:
            # Also remove from user_conversations
            self._remove_conversation_from_user(user_key, conversation_id)

        return result.modified_count > 0

    def _remove_conversation_from_user(self, user_key: str, conversation_id: str):
        """Remove a conversation from user's user_conversations."""
        if self.user_conversations is None:
            return

        self.user_conversations.update_one(
            {'user_key': user_key},
            {
                '$pull': {'conversations': {'conversation_id': conversation_id}},
                '$set': {'updated_at': datetime.utcnow()}
            }
        )
        print(f"REPO: Removed conversation {conversation_id} from user {user_key}")

    def update_conversation(self, conversation_id: str, updates: Dict[str, Any]) -> bool:
        """Update conversation metadata."""
        if self.conversations is None:
            logger.error("Conversations collection not available")
            return False
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
        if self.conversations is None:
            logger.error("Conversations collection not available")
            return False
        op = '$addToSet' if mute else '$pull'
        result = self.conversations.update_one(
            {'conversation_id': conversation_id},
            {op: {'muted_by': user_key}}
        )
        return result.modified_count > 0

    def pin_conversation(self, conversation_id: str, user_key: str, pin: bool = True) -> bool:
        """Pin/unpin conversation for a user."""
        if self.conversations is None:
            logger.error("Conversations collection not available")
            return False
        op = '$addToSet' if pin else '$pull'
        result = self.conversations.update_one(
            {'conversation_id': conversation_id},
            {op: {'pinned_by': user_key}}
        )
        return result.modified_count > 0

    def archive_conversation(self, conversation_id: str, user_key: str, archive: bool = True) -> bool:
        """Archive/unarchive conversation for a user."""
        if self.conversations is None:
            logger.error("Conversations collection not available")
            return False
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
        print(f"REPO: send_message - message_id={message.message_id}, conversation_id={message.conversation_id}")

        if self.messages is None:
            print("REPO: ERROR - Messages collection not available")
            raise RuntimeError("Messages collection not available - MongoDB may not be connected")

        doc = message.to_db_doc()
        doc['created_at'] = datetime.utcnow()

        print(f"REPO: Inserting message document: conversation_id={doc.get('conversation_id')}")

        result = self.messages.insert_one(doc)
        message_id = str(result.inserted_id)
        print(f"REPO: Message inserted with _id={message_id}")

        # Update conversation last_message and last_activity
        if self.conversations is not None:
            update_result = self.conversations.update_one(
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
            print(f"REPO: Conversation updated, matched={update_result.matched_count}, modified={update_result.modified_count}")

        return message_id

    def get_message(self, message_id: str) -> Optional[Dict]:
        """Get message by ID."""
        if self.messages is None:
            logger.error("Messages collection not available")
            return None
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
        print(f"REPO: get_conversation_messages - conversation_id={conversation_id}, limit={limit}")

        if self.messages is None:
            print("REPO: ERROR - Messages collection not available")
            return []

        query = {'conversation_id': conversation_id, 'deleted_at': None}

        if before:
            query['created_at'] = {'$lt': before}
        elif after:
            query['created_at'] = {'$gt': after}

        print(f"REPO: Query: {query}")
        cursor = self.messages.find(query).sort('created_at', -1).limit(limit)
        messages = list(cursor)
        print(f"REPO: Found {len(messages)} messages")
        messages.reverse()  # Return in chronological order
        return messages

    def edit_message(self, message_id: str, sender_key: str, new_content: str) -> bool:
        """Edit a message (only by sender)."""
        if self.messages is None:
            logger.error("Messages collection not available")
            return False
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
        if self.messages is None:
            logger.error("Messages collection not available")
            return False
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

    def clear_conversation(self, conversation_id: str, user_key: str, for_everyone: bool = False) -> int:
        """Clear all messages in a conversation.

        Args:
            conversation_id: The conversation to clear
            user_key: The user clearing the conversation
            for_everyone: If True, deletes messages for all participants (admin only)
                         If False, only hides messages for this user

        Returns:
            Number of messages affected
        """
        if self.messages is None:
            print("REPO: ERROR - Messages collection not available")
            return 0

        print(f"REPO: clear_conversation - conv={conversation_id}, user={user_key}, for_everyone={for_everyone}")

        if for_everyone:
            # Soft delete all messages in conversation (mark as deleted)
            result = self.messages.update_many(
                {'conversation_id': conversation_id, 'deleted_at': None},
                {'$set': {'deleted_at': datetime.utcnow(), 'content': '[Cleared]'}}
            )
            count = result.modified_count

            # Also clear last_message in conversation
            if self.conversations is not None:
                self.conversations.update_one(
                    {'conversation_id': conversation_id},
                    {'$set': {'last_message': None}}
                )
        else:
            # Add user to deleted_for array for all messages (hide for this user only)
            result = self.messages.update_many(
                {'conversation_id': conversation_id},
                {'$addToSet': {'deleted_for': user_key}}
            )
            count = result.modified_count

        print(f"REPO: Cleared {count} messages from conversation {conversation_id}")
        return count

    def search_messages(
        self,
        user_key: str,
        account_key: str,
        query: str,
        conversation_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Search messages by content."""
        if self.messages is None:
            logger.error("Messages collection not available")
            return []

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
        if self.message_receipts is None:
            logger.error("Message receipts collection not available")
            return False
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
        if self.message_receipts is None:
            logger.error("Message receipts collection not available")
            return False
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
        if self.messages is None or self.message_receipts is None:
            logger.error("Messages or message_receipts collection not available")
            return 0

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
        if self.message_receipts is None:
            logger.error("Message receipts collection not available")
            return []
        return list(self.message_receipts.find({'message_id': message_id}))

    def get_unread_count(self, conversation_id: str, user_key: str) -> int:
        """Get unread message count for a conversation."""
        if self.messages is None or self.message_receipts is None:
            logger.error("Messages or message_receipts collection not available")
            return 0

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
        if self.user_presence is None:
            logger.error("User presence collection not available")
            return False
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
        if self.user_presence is None:
            logger.error("User presence collection not available")
            return False
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
        if self.user_presence is None:
            logger.error("User presence collection not available")
            return False
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
        if self.user_presence is None:
            logger.error("User presence collection not available")
            return None
        return self.user_presence.find_one({'user_key': user_key})

    def get_online_users(self, user_keys: List[str]) -> List[Dict]:
        """Get presence for multiple users."""
        if self.user_presence is None:
            logger.error("User presence collection not available")
            return []
        return list(self.user_presence.find({
            'user_key': {'$in': user_keys},
            'status': {'$in': [PresenceStatus.ONLINE, PresenceStatus.TYPING]}
        }))


# Singleton instance
_messaging_repo = None

def get_messaging_repository() -> MessagingRepository:
    """Get singleton messaging repository instance.

    Returns:
        MessagingRepository instance (may have unavailable collections if MongoDB not connected)
    """
    global _messaging_repo
    if _messaging_repo is None:
        _messaging_repo = MessagingRepository()

    # Check availability - this will trigger lazy initialization
    if not _messaging_repo.is_available():
        logger.warning("Messaging repository collections not available - MongoDB may not be connected")
        # Reset the collections_initialized flag to retry on next call
        _messaging_repo._collections_initialized = False

    return _messaging_repo


def reset_messaging_repository():
    """Reset the singleton instance (useful for testing or reconnection)."""
    global _messaging_repo
    if _messaging_repo:
        _messaging_repo._collections_initialized = False
        _messaging_repo._conversations_repo = None
        _messaging_repo._messages_repo = None
        _messaging_repo._receipts_repo = None
        _messaging_repo._presence_repo = None
    _messaging_repo = None


