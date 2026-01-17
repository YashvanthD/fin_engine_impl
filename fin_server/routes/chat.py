"""Chat/Messaging REST API routes.

REST API Endpoints (Initial Load Only):
- GET /api/chat/conversations - List conversations
- GET /api/chat/conversations/{id} - Get conversation details
- GET /api/chat/conversations/{id}/messages - Get message history
- GET /api/chat/search - Search messages
- GET /api/chat/unread - Get unread counts

WebSocket is used for ALL real-time operations (chat:send, chat:read, etc.)
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

    if current_user_key:
        normalized['is_muted'] = current_user_key in normalized.get('muted_by', [])
        normalized['is_pinned'] = current_user_key in normalized.get('pinned_by', [])
        normalized['is_archived'] = current_user_key in normalized.get('archived_by', [])

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

    if current_user_key and current_user_key in normalized.get('deleted_for', []):
        return None

    normalized.pop('deleted_for', None)

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


def _get_unread_count(repo, conversation_id: str, user_key: str) -> int:
    """Get unread count for a conversation."""
    try:
        return repo.get_unread_count(conversation_id, user_key) if hasattr(repo, 'get_unread_count') else 0
    except:
        return 0


def _is_user_online(repo, user_key: str) -> bool:
    """Check if user is online."""
    try:
        presence = repo.get_user_presence(user_key) if hasattr(repo, 'get_user_presence') else None
        return presence.get('status') == 'online' if presence else False
    except:
        return False


# =============================================================================
# Conversation Endpoints
# =============================================================================

@chat_bp.route('/conversations', methods=['GET'])
@handle_errors
@require_auth
def list_conversations(auth_payload):
    """List conversations for the current user with pagination."""
    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')

    limit = min(int(request.args.get('limit', 50)), 100)
    skip = int(request.args.get('skip', 0))
    include_archived = request.args.get('include_archived', 'false').lower() == 'true'
    conv_type = request.args.get('type')

    repo = get_messaging_repository()
    if not repo or not repo.is_available():
        return respond_error('Chat service unavailable', status=503)

    try:
        query = {'participants': user_key, 'account_key': account_key}
        if not include_archived:
            query['archived_by'] = {'$ne': user_key}
        if conv_type:
            query['conversation_type'] = conv_type

        if repo.conversations is None:
            return respond_error('Chat service unavailable', status=503)

        cursor = repo.conversations.find(query).sort('last_activity', -1).skip(skip).limit(limit + 1)
        conversations = list(cursor)

        has_more = len(conversations) > limit
        if has_more:
            conversations = conversations[:limit]

        result = []
        for conv in conversations:
            normalized = _normalize_conversation(conv, user_key)
            if normalized:
                normalized['unread_count'] = _get_unread_count(repo, normalized['id'], user_key)
                result.append(normalized)

        logger.debug(f"list_convs: user={user_key[:8]}..., count={len(result)}")

        return respond_success({
            'conversations': result,
            'count': len(result),
            'has_more': has_more,
            'meta': {'limit': limit, 'skip': skip}
        })

    except Exception as e:
        logger.error(f'list_convs error: {e}')
        return respond_error('Failed to list conversations', status=500)


@chat_bp.route('/conversations/<conversation_id>', methods=['GET'])
@handle_errors
@require_auth
def get_conversation(conversation_id, auth_payload):
    """Get conversation details."""
    user_key = auth_payload.get('user_key')

    repo = get_messaging_repository()
    if not repo or not repo.is_available():
        return respond_error('Chat service unavailable', status=503)

    try:
        conv = repo.get_conversation(conversation_id, user_key)
        if not conv:
            return respond_error('Conversation not found', status=404)

        if user_key not in conv.get('participants', []):
            return respond_error('Not authorized', status=403)

        normalized = _normalize_conversation(conv, user_key)
        normalized['unread_count'] = _get_unread_count(repo, conversation_id, user_key)

        user_repo = get_collection('users')
        if user_repo is not None:
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
        logger.error(f'get_conv error: {e}')
        return respond_error('Failed to get conversation', status=500)


@chat_bp.route('/conversations/<conversation_id>/messages', methods=['GET'])
@handle_errors
@require_auth
def get_messages(conversation_id, auth_payload):
    """Get messages in a conversation with pagination."""
    user_key = auth_payload.get('user_key')

    limit = min(int(request.args.get('limit', 50)), 100)
    before = _parse_datetime(request.args.get('before'))
    after = _parse_datetime(request.args.get('after'))

    repo = get_messaging_repository()
    if not repo or not repo.is_available():
        return respond_error('Chat service unavailable', status=503)

    try:
        conv = repo.get_conversation(conversation_id, user_key)
        if not conv:
            return respond_error('Conversation not found', status=404)

        if user_key not in conv.get('participants', []):
            return respond_error('Not authorized', status=403)

        if repo.messages is None:
            return respond_error('Chat service unavailable', status=503)

        query = {
            'conversation_id': conversation_id,
            'deleted_at': None,
            'deleted_for': {'$ne': user_key}
        }

        if before:
            query['created_at'] = {'$lt': before}
        elif after:
            query['created_at'] = {'$gt': after}

        sort_order = -1 if not after else 1
        cursor = repo.messages.find(query).sort('created_at', sort_order).limit(limit + 1)
        messages = list(cursor)

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        if sort_order == -1:
            messages.reverse()

        result = [_normalize_message(msg, user_key) for msg in messages if _normalize_message(msg, user_key)]

        response = {
            'messages': result,
            'count': len(result),
            'has_more': has_more
        }

        if result:
            response['oldest_timestamp'] = result[0].get('created_at')
            response['newest_timestamp'] = result[-1].get('created_at')

        logger.debug(f"get_msgs: conv={conversation_id[:12]}..., count={len(result)}")

        return respond_success(response)

    except Exception as e:
        logger.error(f'get_msgs error: {e}')
        return respond_error('Failed to get messages', status=500)


# =============================================================================
# Search Endpoint
# =============================================================================

@chat_bp.route('/search', methods=['GET'])
@handle_errors
@require_auth
def search_messages(auth_payload):
    """Search messages across conversations."""
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

    logger.debug(f"GET /api/chat/presence | account_key: {account_key}, checking: {len(user_keys)} users")

    repo = get_messaging_repository()
    if not repo or not repo.is_available():
        return respond_error('Chat service unavailable', status=503)

    try:
        presence_data = {}

        if repo.user_presence is None:
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

