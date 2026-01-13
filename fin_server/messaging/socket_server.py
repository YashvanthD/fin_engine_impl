"""Enhanced Socket.IO server with WhatsApp/Telegram-like features.

Features:
- Real-time messaging
- Typing indicators
- Read receipts (single/double tick)
- Online/offline presence
- Group chats
- Message reactions
- Reply to messages
- Forward messages
- Delete for everyone
"""
import logging
from datetime import datetime
from threading import Thread
from typing import Optional, Dict, Any

from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect

from fin_server.repository.mongo_helper import get_collection
from fin_server.security.authentication import AuthSecurity
from fin_server.messaging.models import (
    Message, Conversation, MessageType, MessageStatus,
    ConversationType, PresenceStatus
)
from fin_server.messaging.repository import get_messaging_repository
from fin_server.utils.generator import generate_message_id, generate_conversation_id

logger = logging.getLogger(__name__)

# Socket.IO instance - will be initialized with Flask app
socketio = SocketIO(
    async_mode='threading',
    cors_allowed_origins="*",
    ping_timeout=60,
    ping_interval=25
)

# Connected users: {socket_id: {user_key, account_key, rooms}}
connected_users: Dict[str, Dict[str, Any]] = {}

# User to socket mapping: {user_key: [socket_ids]} (supports multiple devices)
user_sockets: Dict[str, list] = {}

# Legacy repos for backward compatibility
notification_queue_repo = get_collection('notification_queue')
user_repo = get_collection('users')


def authenticate_socket(token: str) -> Optional[Dict]:
    """Authenticate socket connection using JWT token."""
    try:
        payload = AuthSecurity.decode_token(token)
        return payload
    except Exception as e:
        logger.warning(f"Socket authentication failed: {e}")
        return None


def get_user_from_socket(socket_id: str = None) -> Optional[Dict]:
    """Get user info from socket connection."""
    sid = socket_id or request.sid
    return connected_users.get(sid)


def emit_to_user(user_key: str, event: str, data: Any):
    """Emit event to all connected devices of a user."""
    sockets = user_sockets.get(user_key, [])
    for sid in sockets:
        socketio.emit(event, data, room=sid)


def emit_to_conversation(conversation_id: str, event: str, data: Any, exclude_sender: str = None):
    """Emit event to all participants in a conversation."""
    repo = get_messaging_repository()
    conv = repo.get_conversation(conversation_id)
    if conv:
        for participant in conv.get('participants', []):
            if participant != exclude_sender:
                emit_to_user(participant, event, data)


# =============================================================================
# Connection Events
# =============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle new socket connection."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')

    # Try query param if header not present
    if not token:
        token = request.args.get('token', '')

    payload = authenticate_socket(token)
    if not payload:
        emit('error', {'code': 'UNAUTHORIZED', 'message': 'Invalid or missing token'})
        disconnect()
        return

    user_key = payload.get('user_key')
    account_key = payload.get('account_key')
    socket_id = request.sid

    # Store connection
    connected_users[socket_id] = {
        'user_key': user_key,
        'account_key': account_key,
        'connected_at': datetime.utcnow().isoformat()
    }

    # Add to user's socket list (support multiple devices)
    if user_key not in user_sockets:
        user_sockets[user_key] = []
    user_sockets[user_key].append(socket_id)

    # Join user's personal room and account room
    join_room(user_key)
    join_room(account_key)

    # Update presence
    repo = get_messaging_repository()
    device_info = {
        'user_agent': request.headers.get('User-Agent'),
        'ip': request.remote_addr
    }
    repo.set_user_online(user_key, socket_id, device_info)

    # Join all user's conversations
    conversations = repo.get_user_conversations(user_key, account_key)
    for conv in conversations:
        conv_id = conv.get('conversation_id') or str(conv.get('_id'))
        join_room(f"conv:{conv_id}")

    # Notify contacts that user is online
    broadcast_presence(user_key, PresenceStatus.ONLINE)

    # Send connection success
    emit('connected', {
        'message': 'Connected to messaging service',
        'user_key': user_key,
        'socket_id': socket_id
    })

    # Send pending messages/notifications
    send_pending_messages(user_key)

    logger.info(f"User {user_key} connected (socket: {socket_id})")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle socket disconnection."""
    socket_id = request.sid
    user_info = connected_users.pop(socket_id, None)

    if user_info:
        user_key = user_info.get('user_key')

        # Remove from user's socket list
        if user_key in user_sockets:
            user_sockets[user_key] = [s for s in user_sockets[user_key] if s != socket_id]

            # If no more connections, set offline
            if not user_sockets[user_key]:
                del user_sockets[user_key]
                repo = get_messaging_repository()
                repo.set_user_offline(user_key)
                broadcast_presence(user_key, PresenceStatus.OFFLINE)

        logger.info(f"User {user_key} disconnected (socket: {socket_id})")


# =============================================================================
# Messaging Events
# =============================================================================

@socketio.on('message:send')
def handle_send_message(data):
    """Handle sending a new message."""
    user_info = get_user_from_socket()
    if not user_info:
        emit('error', {'code': 'UNAUTHORIZED', 'message': 'Not authenticated'})
        return

    user_key = user_info['user_key']
    account_key = user_info['account_key']

    conversation_id = data.get('conversationId') or data.get('conversation_id')
    content = data.get('content') or data.get('message')
    message_type = data.get('messageType') or data.get('type', MessageType.TEXT)
    reply_to = data.get('replyTo') or data.get('reply_to')

    if not conversation_id or not content:
        emit('error', {'code': 'INVALID_DATA', 'message': 'conversationId and content required'})
        return

    repo = get_messaging_repository()

    # Verify user is participant
    conv = repo.get_conversation(conversation_id, user_key)
    if not conv:
        emit('error', {'code': 'NOT_FOUND', 'message': 'Conversation not found'})
        return

    # Create message
    message = Message(
        message_id=generate_message_id(),
        conversation_id=conversation_id,
        sender_key=user_key,
        content=content,
        message_type=message_type,
        reply_to=reply_to,
        media_url=data.get('mediaUrl'),
        mentions=data.get('mentions', []),
        account_key=account_key
    )

    message_id = repo.send_message(message)
    message.message_id = message_id

    # Build response
    message_data = message.to_dict()
    message_data['status'] = MessageStatus.SENT

    # Send to sender (confirmation)
    emit('message:sent', message_data)

    # Send to all other participants
    for participant in conv.get('participants', []):
        if participant != user_key:
            emit_to_user(participant, 'message:new', message_data)
            # Mark as delivered if user is online
            if participant in user_sockets:
                repo.mark_delivered(message_id, participant)
                emit('message:delivered', {
                    'messageId': message_id,
                    'deliveredTo': participant,
                    'timestamp': datetime.utcnow().isoformat()
                })

    logger.info(f"Message {message_id} sent by {user_key} in {conversation_id}")


@socketio.on('message:edit')
def handle_edit_message(data):
    """Handle editing a message."""
    user_info = get_user_from_socket()
    if not user_info:
        emit('error', {'code': 'UNAUTHORIZED', 'message': 'Not authenticated'})
        return

    message_id = data.get('messageId') or data.get('message_id')
    new_content = data.get('content')

    if not message_id or not new_content:
        emit('error', {'code': 'INVALID_DATA', 'message': 'messageId and content required'})
        return

    repo = get_messaging_repository()
    success = repo.edit_message(message_id, user_info['user_key'], new_content)

    if success:
        msg = repo.get_message(message_id)
        conversation_id = msg.get('conversation_id')

        edit_data = {
            'messageId': message_id,
            'content': new_content,
            'editedAt': datetime.utcnow().isoformat()
        }

        emit('message:edited', edit_data)
        emit_to_conversation(conversation_id, 'message:edited', edit_data, user_info['user_key'])
    else:
        emit('error', {'code': 'EDIT_FAILED', 'message': 'Could not edit message'})


@socketio.on('message:delete')
def handle_delete_message(data):
    """Handle deleting a message."""
    user_info = get_user_from_socket()
    if not user_info:
        emit('error', {'code': 'UNAUTHORIZED', 'message': 'Not authenticated'})
        return

    message_id = data.get('messageId') or data.get('message_id')
    for_everyone = data.get('forEveryone', False)

    if not message_id:
        emit('error', {'code': 'INVALID_DATA', 'message': 'messageId required'})
        return

    repo = get_messaging_repository()
    msg = repo.get_message(message_id)

    if not msg:
        emit('error', {'code': 'NOT_FOUND', 'message': 'Message not found'})
        return

    success = repo.delete_message(message_id, user_info['user_key'], for_everyone)

    if success:
        delete_data = {
            'messageId': message_id,
            'deletedAt': datetime.utcnow().isoformat(),
            'forEveryone': for_everyone
        }

        emit('message:deleted', delete_data)

        if for_everyone:
            emit_to_conversation(
                msg.get('conversation_id'),
                'message:deleted',
                delete_data,
                user_info['user_key']
            )


@socketio.on('message:read')
def handle_read_message(data):
    """Handle marking messages as read."""
    user_info = get_user_from_socket()
    if not user_info:
        return

    message_id = data.get('messageId') or data.get('message_id')
    conversation_id = data.get('conversationId') or data.get('conversation_id')

    repo = get_messaging_repository()

    if conversation_id:
        # Mark all messages in conversation as read
        count = repo.mark_conversation_read(conversation_id, user_info['user_key'])
        conv = repo.get_conversation(conversation_id)

        # Notify senders their messages were read
        emit_to_conversation(conversation_id, 'message:read', {
            'conversationId': conversation_id,
            'readBy': user_info['user_key'],
            'timestamp': datetime.utcnow().isoformat()
        }, user_info['user_key'])

    elif message_id:
        repo.mark_read(message_id, user_info['user_key'])
        msg = repo.get_message(message_id)

        if msg:
            emit_to_user(msg.get('sender_key'), 'message:read', {
                'messageId': message_id,
                'readBy': user_info['user_key'],
                'timestamp': datetime.utcnow().isoformat()
            })


# =============================================================================
# Typing Indicators
# =============================================================================

@socketio.on('typing:start')
def handle_typing_start(data):
    """Handle user started typing."""
    user_info = get_user_from_socket()
    if not user_info:
        return

    conversation_id = data.get('conversationId') or data.get('conversation_id')
    if not conversation_id:
        return

    repo = get_messaging_repository()
    repo.set_user_typing(user_info['user_key'], conversation_id, True)

    emit_to_conversation(conversation_id, 'typing:update', {
        'conversationId': conversation_id,
        'userKey': user_info['user_key'],
        'isTyping': True
    }, user_info['user_key'])


@socketio.on('typing:stop')
def handle_typing_stop(data):
    """Handle user stopped typing."""
    user_info = get_user_from_socket()
    if not user_info:
        return

    conversation_id = data.get('conversationId') or data.get('conversation_id')
    if not conversation_id:
        return

    repo = get_messaging_repository()
    repo.set_user_typing(user_info['user_key'], conversation_id, False)

    emit_to_conversation(conversation_id, 'typing:update', {
        'conversationId': conversation_id,
        'userKey': user_info['user_key'],
        'isTyping': False
    }, user_info['user_key'])


# =============================================================================
# Conversation Events
# =============================================================================

@socketio.on('conversation:create')
def handle_create_conversation(data):
    """Handle creating a new conversation."""
    user_info = get_user_from_socket()
    if not user_info:
        emit('error', {'code': 'UNAUTHORIZED', 'message': 'Not authenticated'})
        return

    user_key = user_info['user_key']
    account_key = user_info['account_key']

    participants = data.get('participants', [])
    if user_key not in participants:
        participants.append(user_key)

    conv_type = data.get('type', ConversationType.DIRECT)
    if len(participants) == 2:
        conv_type = ConversationType.DIRECT
    elif len(participants) > 2:
        conv_type = ConversationType.GROUP

    conversation = Conversation(
        conversation_id=generate_conversation_id(),
        conversation_type=conv_type,
        participants=participants,
        name=data.get('name'),
        description=data.get('description'),
        created_by=user_key,
        admins=[user_key] if conv_type == ConversationType.GROUP else [],
        account_key=account_key
    )

    repo = get_messaging_repository()
    conv_id = repo.create_conversation(conversation)
    conversation.conversation_id = conv_id

    # Join room for this conversation
    join_room(f"conv:{conv_id}")

    # Notify all participants
    conv_data = conversation.to_dict()
    for participant in participants:
        emit_to_user(participant, 'conversation:created', conv_data)

    emit('conversation:created', conv_data)


@socketio.on('conversation:join')
def handle_join_conversation(data):
    """Handle joining a conversation room."""
    user_info = get_user_from_socket()
    if not user_info:
        return

    conversation_id = data.get('conversationId') or data.get('conversation_id')
    if conversation_id:
        join_room(f"conv:{conversation_id}")
        emit('conversation:joined', {'conversationId': conversation_id})


@socketio.on('conversation:leave')
def handle_leave_conversation(data):
    """Handle leaving a conversation room."""
    user_info = get_user_from_socket()
    if not user_info:
        return

    conversation_id = data.get('conversationId') or data.get('conversation_id')
    if conversation_id:
        leave_room(f"conv:{conversation_id}")


# =============================================================================
# Presence Events
# =============================================================================

@socketio.on('presence:subscribe')
def handle_presence_subscribe(data):
    """Subscribe to presence updates for specific users."""
    user_info = get_user_from_socket()
    if not user_info:
        return

    user_keys = data.get('userKeys', [])
    repo = get_messaging_repository()

    presences = repo.get_online_users(user_keys)
    presence_map = {p['user_key']: p.get('status', PresenceStatus.OFFLINE) for p in presences}

    # Fill in offline users
    for uk in user_keys:
        if uk not in presence_map:
            presence_map[uk] = PresenceStatus.OFFLINE

    emit('presence:status', {'presences': presence_map})


def broadcast_presence(user_key: str, status: str):
    """Broadcast user's presence to their contacts."""
    repo = get_messaging_repository()
    # Get all users who share conversations with this user
    # For simplicity, broadcast to account room
    user_info = connected_users.get(request.sid) if hasattr(request, 'sid') else None
    if user_info:
        socketio.emit('presence:update', {
            'userKey': user_key,
            'status': status,
            'timestamp': datetime.utcnow().isoformat()
        }, room=user_info.get('account_key'))


# =============================================================================
# Legacy Notification Support
# =============================================================================

@socketio.on('send_notification')
def handle_send_notification(data):
    """Legacy notification handler for backward compatibility."""
    user_info = get_user_from_socket()
    if not user_info:
        emit('error', {'error': 'Unauthorized'})
        return

    to_user_key = data.get('to_user_key')
    message = data.get('message')
    notif_type = data.get('type', 'info')

    notification = {
        'user_key': to_user_key,
        'from_user_key': user_info['user_key'],
        'message': message,
        'type': notif_type,
        'timestamp': datetime.utcnow().isoformat()
    }

    notification_queue_repo.enqueue(notification)
    emit_to_user(to_user_key, 'notification', notification)


# =============================================================================
# Helper Functions
# =============================================================================

def send_pending_messages(user_key: str):
    """Send pending messages to user on connect."""
    repo = get_messaging_repository()

    # Get pending notifications
    pending = notification_queue_repo.get_pending(user_key=user_key)
    for n in pending:
        emit('notification', n)
        notification_queue_repo.mark_sent(n['_id'])


# Background worker for offline delivery
def notification_worker():
    """Background worker to deliver pending notifications."""
    import time
    while True:
        try:
            pending = notification_queue_repo.get_pending()
            for n in pending:
                user_key = n.get('user_key')
                if user_key and user_key in user_sockets:
                    emit_to_user(user_key, 'notification', n)
                    notification_queue_repo.mark_sent(n['_id'])
        except Exception as e:
            logger.exception(f"Notification worker error: {e}")
        time.sleep(10)


def start_notification_worker():
    """Start the background notification worker."""
    t = Thread(target=notification_worker, daemon=True)
    t.start()
    logger.info("Notification worker started")

