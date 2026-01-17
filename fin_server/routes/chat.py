"""Chat/Messaging REST API routes.

This module provides REST API endpoints for chat operations.
These endpoints are used ONLY for initial data loading.

WebSocket is used for ALL real-time operations:
- Sending/receiving messages (chat:send, chat:message)
- Typing indicators (chat:typing)
- Read receipts (chat:read)
- Message edits/deletes (chat:edit, chat:delete)
- Presence updates (chat:presence)

REST API Endpoints (Initial Load Only):
- GET /api/chat/conversations - List conversations (initial load)
- GET /api/chat/conversations/{id} - Get conversation details
- GET /api/chat/conversations/{id}/messages - Get message history (initial/pagination)
- GET /api/chat/search - Search messages
- GET /api/chat/unread - Get unread counts

WebSocket Events (Real-time):
- chat:send -> chat:message:sent, chat:message (new message)
- chat:read -> chat:message:read (read receipt)
- chat:typing -> chat:typing:start/stop (typing indicator)
- chat:edit -> chat:message:edited (edit message)
- chat:delete -> chat:message:deleted (delete message)
- chat:conversation:create -> chat:conversation:created (new conversation)

Collections (separate from other modules):
- conversations: Chat conversations
- chat_messages: Chat messages
- message_receipts: Read/delivery receipts
- user_presence: Online/offline status
"""
import logging
from datetime import datetime
from typing import Optional

from flask import Blueprint, request

from fin_server.messaging.repository import get_messaging_repository
from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.decorators import handle_errors, require_auth
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc

logger = logging.getLogger(__name__)

# Blueprint
chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')


# =============================================================================
# Helper Functions
# =============================================================================

def _normalize_conversation(doc, current_user_key: str = None):
    """Normalize conversation document for API response."""
    if not doc:
        return None

    normalized = normalize_doc(doc)
    normalized['id'] = normalized.get('conversation_id') or str(normalized.get('_id', ''))
    normalized['conversation_id'] = normalized['id']

    # Add computed fields
    if current_user_key:
        normalized['is_muted'] = current_user_key in normalized.get('muted_by', [])
        normalized['is_pinned'] = current_user_key in normalized.get('pinned_by', [])
        normalized['is_archived'] = current_user_key in normalized.get('archived_by', [])

    # Remove internal arrays from response
    for field in ['muted_by', 'pinned_by', 'archived_by', 'deleted_for']:
        normalized.pop(field, None)

    return normalized


def _normalize_message(doc, current_user_key: str = None):
    """Normalize message document for API response."""
    if not doc:
        return None

    normalized = normalize_doc(doc)
    normalized['id'] = normalized.get('message_id') or str(normalized.get('_id', ''))
    normalized['message_id'] = normalized['id']

    # Check if deleted for this user
    if current_user_key and current_user_key in normalized.get('deleted_for', []):
        return None  # Don't return messages deleted for this user

    # Remove internal fields
    normalized.pop('deleted_for', None)

    # Format timestamps
    for ts_field in ['created_at', 'edited_at', 'deleted_at']:
        if normalized.get(ts_field) and hasattr(normalized[ts_field], 'isoformat'):
            normalized[ts_field] = normalized[ts_field].isoformat()

    return normalized


def _parse_datetime(value: str) -> Optional[datetime]:
    """Parse datetime from string."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except:
        try:
            return datetime.fromtimestamp(float(value))
        except:
            return None


# =============================================================================
# Conversation Endpoints
# =============================================================================

@chat_bp.route('/conversations', methods=['GET'])
@handle_errors
@require_auth
def list_conversations(auth_payload):
    """List conversations for the current user with pagination.

    Query Params:
        limit: int - Max results (default: 50, max: 100)
        skip: int - Offset for pagination
        include_archived: bool - Include archived conversations
        type: str - Filter by type (direct, group)

    Response:
        {
            "conversations": [...],
            "count": 10,
            "has_more": true,
            "meta": { "limit": 50, "skip": 0 }
        }
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    print(f"CHAT_ROUTE: GET /api/chat/conversations | user_key={user_key}, account_key={account_key}")

    # Parse query params
    limit = min(int(request.args.get('limit', 50)), 100)
    skip = int(request.args.get('skip', 0))
    include_archived = request.args.get('include_archived', 'false').lower() == 'true'
    conv_type = request.args.get('type')

    repo = get_messaging_repository()
    if not repo or not repo.is_available():
        print("CHAT_ROUTE: ERROR - Chat service unavailable")
        return respond_error('Chat service unavailable', status=503)

    try:
        # Build query
        query = {
            'participants': user_key,
            'account_key': account_key
        }

        if not include_archived:
            query['archived_by'] = {'$ne': user_key}

        if conv_type:
            query['conversation_type'] = conv_type

        print(f"CHAT_ROUTE: Query: {query}")

        # Get conversations
        if repo.conversations is None:
            print("CHAT_ROUTE: ERROR - Conversations collection not available")
            return respond_error('Chat service unavailable', status=503)

        cursor = repo.conversations.find(query).sort('last_activity', -1).skip(skip).limit(limit + 1)
        conversations = list(cursor)
        print(f"CHAT_ROUTE: Found {len(conversations)} conversations")

        # Debug: show found conversations
        for conv in conversations[:5]:
            print(f"CHAT_ROUTE:   - id={conv.get('conversation_id')}, participants={conv.get('participants')}")

        # Check if there are more
        has_more = len(conversations) > limit
        if has_more:
            conversations = conversations[:limit]

        # Normalize and add unread counts
        result = []
        for conv in conversations:
            normalized = _normalize_conversation(conv, user_key)
            if normalized:
                # Get unread count for this conversation
                normalized['unread_count'] = _get_unread_count(
                    repo, normalized['id'], user_key
                )
                result.append(normalized)

        return respond_success({
            'conversations': result,
            'count': len(result),
            'has_more': has_more,
            'meta': {'limit': limit, 'skip': skip}
        })

    except Exception as e:
        logger.exception(f'Error listing conversations: {e}')
        return respond_error('Failed to list conversations', status=500)


@chat_bp.route('/conversations/<conversation_id>', methods=['GET'])
@handle_errors
@require_auth
def get_conversation(conversation_id, auth_payload):
    """Get conversation details.

    Response includes:
        - Conversation metadata
        - Participant list
        - Unread count
        - Last message preview
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"GET /api/chat/conversations/{conversation_id} | account_key: {account_key}, user_key: {user_key}")

    repo = get_messaging_repository()
    if not repo or not repo.is_available():
        return respond_error('Chat service unavailable', status=503)

    try:
        conv = repo.get_conversation(conversation_id, user_key)

        if not conv:
            return respond_error('Conversation not found', status=404)

        # Verify user is participant
        if user_key not in conv.get('participants', []):
            return respond_error('Not authorized to view this conversation', status=403)

        normalized = _normalize_conversation(conv, user_key)
        normalized['unread_count'] = _get_unread_count(repo, conversation_id, user_key)

        # Get participant details
        user_repo = get_collection('users')
        if user_repo:
            participants_info = []
            for p_key in conv.get('participants', []):
                user = user_repo.find_one({'user_key': p_key})
                if user:
                    participants_info.append({
                        'user_key': p_key,
                        'name': user.get('name') or user.get('username'),
                        'avatar_url': user.get('avatar_url'),
                        'is_online': _is_user_online(repo, p_key)
                    })
            normalized['participants_info'] = participants_info

        return respond_success({'conversation': normalized})

    except Exception as e:
        logger.exception(f'Error getting conversation: {e}')
        return respond_error('Failed to get conversation', status=500)


@chat_bp.route('/conversations/<conversation_id>/messages', methods=['GET'])
@handle_errors
@require_auth
def get_messages(conversation_id, auth_payload):
    """Get messages in a conversation with pagination.

    Query Params:
        limit: int - Max results (default: 50, max: 100)
        before: datetime - Get messages before this timestamp (for older messages)
        after: datetime - Get messages after this timestamp (for newer messages)

    Response:
        {
            "messages": [...],
            "count": 50,
            "has_more": true,
            "oldest_timestamp": "2026-01-17T10:00:00Z",
            "newest_timestamp": "2026-01-17T12:00:00Z"
        }
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    print(f"CHAT_ROUTE: GET messages - conversation_id={conversation_id}, user_key={user_key}")

    # Parse query params
    limit = min(int(request.args.get('limit', 50)), 100)
    before = _parse_datetime(request.args.get('before'))
    after = _parse_datetime(request.args.get('after'))

    repo = get_messaging_repository()
    if not repo or not repo.is_available():
        print("CHAT_ROUTE: ERROR - Chat service unavailable")
        return respond_error('Chat service unavailable', status=503)

    try:
        # Verify user has access to conversation
        print(f"CHAT_ROUTE: Checking conversation access...")
        conv = repo.get_conversation(conversation_id, user_key)
        if not conv:
            print(f"CHAT_ROUTE: ERROR - Conversation not found or no access")
            return respond_error('Conversation not found', status=404)

        participants = conv.get('participants', [])
        print(f"CHAT_ROUTE: Conversation found, participants={participants}")

        if user_key not in participants:
            print(f"CHAT_ROUTE: ERROR - User {user_key} not in participants {participants}")
            return respond_error('Not authorized to view this conversation', status=403)

        print(f"CHAT_ROUTE: Access verified, loading messages...")

        # Check if messages collection is available
        if repo.messages is None:
            print("CHAT_ROUTE: ERROR - Messages collection not available")
            return respond_error('Chat service unavailable', status=503)

        # Build query
        query = {
            'conversation_id': conversation_id,
            'deleted_at': None,
            'deleted_for': {'$ne': user_key}
        }

        if before:
            query['created_at'] = {'$lt': before}
        elif after:
            query['created_at'] = {'$gt': after}

        print(f"CHAT_ROUTE: Query: {query}")

        # Get messages (fetch one extra to check has_more)
        sort_order = -1  # Newest first when loading older messages
        if after:
            sort_order = 1  # Oldest first when loading newer messages

        cursor = repo.messages.find(query).sort('created_at', sort_order).limit(limit + 1)
        messages = list(cursor)
        print(f"CHAT_ROUTE: Found {len(messages)} messages")

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        # Reverse to get chronological order if we fetched newest first
        if sort_order == -1:
            messages.reverse()

        # Normalize messages
        result = []
        for msg in messages:
            normalized = _normalize_message(msg, user_key)
            if normalized:
                result.append(normalized)

        response = {
            'messages': result,
            'count': len(result),
            'has_more': has_more
        }

        if result:
            response['oldest_timestamp'] = result[0].get('created_at')
            response['newest_timestamp'] = result[-1].get('created_at')

        return respond_success(response)

    except Exception as e:
        logger.exception(f'Error getting messages: {e}')
        return respond_error('Failed to get messages', status=500)


# =============================================================================
# Search Endpoint
# =============================================================================

@chat_bp.route('/search', methods=['GET'])
@handle_errors
@require_auth
def search_messages(auth_payload):
    """Search messages across conversations.

    Query Params:
        q: str - Search query (required)
        conversation_id: str - Limit search to specific conversation
        limit: int - Max results (default: 50, max: 100)

    Response:
        {
            "messages": [...],
            "count": 10
        }
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')

    query_text = request.args.get('q', '').strip()
    if not query_text or len(query_text) < 2:
        return respond_error('Search query must be at least 2 characters', status=400)

    conversation_id = request.args.get('conversation_id')
    limit = min(int(request.args.get('limit', 50)), 100)

    logger.info(f"GET /api/chat/search?q={query_text} | account_key: {account_key}, user_key: {user_key}")

    repo = get_messaging_repository()
    if not repo or not repo.is_available():
        return respond_error('Chat service unavailable', status=503)

    try:
        messages = repo.search_messages(
            user_key=user_key,
            account_key=account_key,
            query=query_text,
            conversation_id=conversation_id,
            limit=limit
        )

        result = []
        for msg in messages:
            normalized = _normalize_message(msg, user_key)
            if normalized:
                # Add conversation info for context
                conv = repo.get_conversation(msg.get('conversation_id'))
                if conv:
                    normalized['conversation_name'] = conv.get('name') or 'Direct Message'
                    normalized['conversation_type'] = conv.get('conversation_type')
                result.append(normalized)

        return respond_success({
            'messages': result,
            'count': len(result),
            'query': query_text
        })

    except Exception as e:
        logger.exception(f'Error searching messages: {e}')
        return respond_error('Failed to search messages', status=500)


# =============================================================================
# Unread Count Endpoint
# =============================================================================

@chat_bp.route('/unread', methods=['GET'])
@handle_errors
@require_auth
def get_unread_counts(auth_payload):
    """Get unread message counts.

    Response:
        {
            "total_unread": 15,
            "conversations": {
                "conv_123": 5,
                "conv_456": 10
            }
        }
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')
    logger.info(f"GET /api/chat/unread | account_key: {account_key}, user_key: {user_key}")

    repo = get_messaging_repository()
    if not repo or not repo.is_available():
        return respond_error('Chat service unavailable', status=503)

    try:
        # Get user's conversations
        conversations = repo.get_user_conversations(user_key, account_key, limit=100)

        total_unread = 0
        conversation_counts = {}

        for conv in conversations:
            conv_id = conv.get('conversation_id') or str(conv.get('_id'))
            unread = _get_unread_count(repo, conv_id, user_key)
            if unread > 0:
                conversation_counts[conv_id] = unread
                total_unread += unread

        return respond_success({
            'total_unread': total_unread,
            'conversations': conversation_counts
        })

    except Exception as e:
        logger.exception(f'Error getting unread counts: {e}')
        return respond_error('Failed to get unread counts', status=500)


# =============================================================================
# Presence Endpoint
# =============================================================================

@chat_bp.route('/presence', methods=['GET'])
@handle_errors
@require_auth
def get_presence(auth_payload):
    """Get online status of users.

    Query Params:
        user_keys: str - Comma-separated user keys to check

    Response:
        {
            "presence": {
                "user_123": { "status": "online", "last_seen": null },
                "user_456": { "status": "offline", "last_seen": "2026-01-17T10:00:00Z" }
            }
        }
    """
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')

    user_keys_str = request.args.get('user_keys', '')
    user_keys = [k.strip() for k in user_keys_str.split(',') if k.strip()]

    if not user_keys:
        return respond_error('user_keys parameter required', status=400)

    logger.info(f"GET /api/chat/presence | account_key: {account_key}, checking: {len(user_keys)} users")

    repo = get_messaging_repository()
    if not repo or not repo.is_available():
        return respond_error('Chat service unavailable', status=503)

    try:
        presence_data = {}

        if repo.user_presence is None:
            # Return offline for all users if presence collection not available
            for uk in user_keys[:50]:
                presence_data[uk] = {'status': 'offline', 'last_seen': None}
            return respond_success({'presence': presence_data})

        for uk in user_keys[:50]:  # Limit to 50 users per request
            presence = repo.user_presence.find_one({'user_key': uk})
            if presence:
                status = presence.get('status', 'offline')
                last_seen = presence.get('last_seen')
                if last_seen and hasattr(last_seen, 'isoformat'):
                    last_seen = last_seen.isoformat()
                presence_data[uk] = {
                    'status': status,
                    'last_seen': last_seen if status == 'offline' else None
                }
            else:
                presence_data[uk] = {
                    'status': 'offline',
                    'last_seen': None
                }

        return respond_success({'presence': presence_data})

    except Exception as e:
        logger.exception(f'Error getting presence: {e}')
        return respond_error('Failed to get presence', status=500)


# =============================================================================
# Helper Functions
# =============================================================================

def _get_unread_count(repo, conversation_id: str, user_key: str) -> int:
    """Get unread message count for a conversation."""
    try:
        # Get user's last read timestamp for this conversation
        receipt = repo.message_receipts.find_one({
            'conversation_id': conversation_id,
            'user_key': user_key,
            'type': 'read'
        }, sort=[('timestamp', -1)])

        last_read = receipt.get('timestamp') if receipt else None

        # Count messages after last read
        query = {
            'conversation_id': conversation_id,
            'sender_key': {'$ne': user_key},  # Not own messages
            'deleted_at': None,
            'deleted_for': {'$ne': user_key}
        }

        if last_read:
            query['created_at'] = {'$gt': last_read}

        return repo.messages.count_documents(query)
    except:
        return 0


def _is_user_online(repo, user_key: str) -> bool:
    """Check if a user is online."""
    try:
        presence = repo.user_presence.find_one({'user_key': user_key})
        return presence and presence.get('status') == 'online'
    except:
        return False
