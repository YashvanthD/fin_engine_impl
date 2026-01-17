"""WebSocket Chat Handler.

Handles real-time chat operations via WebSocket.
REST API is only for initial load and history.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from flask_socketio import emit, join_room, leave_room

from fin_server.messaging.repository import get_messaging_repository
from fin_server.messaging.models import (
    Message, Conversation, MessageType, MessageStatus,
    ConversationType
)
from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.generator import generate_message_id, generate_conversation_id

logger = logging.getLogger(__name__)


class ChatHandler:
    """Handler for WebSocket chat events."""

    # Event names
    EVENT_MESSAGE_NEW = 'chat:message'
    EVENT_MESSAGE_SENT = 'chat:message:sent'
    EVENT_MESSAGE_DELIVERED = 'chat:message:delivered'
    EVENT_MESSAGE_READ = 'chat:message:read'
    EVENT_MESSAGE_EDITED = 'chat:message:edited'
    EVENT_MESSAGE_DELETED = 'chat:message:deleted'
    EVENT_TYPING_START = 'chat:typing:start'
    EVENT_TYPING_STOP = 'chat:typing:stop'
    EVENT_CONVERSATION_CREATED = 'chat:conversation:created'
    EVENT_CONVERSATION_UPDATED = 'chat:conversation:updated'
    EVENT_PRESENCE_UPDATE = 'chat:presence'
    EVENT_ERROR = 'chat:error'

    def __init__(self, socketio, connected_users: Dict, user_sockets: Dict):
        self.socketio = socketio
        self.connected_users = connected_users
        self.user_sockets = user_sockets

    def register_handlers(self):
        """Register chat WebSocket event handlers."""
        logger.info("CHAT: registering handlers")

        # =====================================================================
        # Message Events
        # =====================================================================

        @self.socketio.on('chat:send')
        def handle_send_message(data):
            """Handle sending a new message."""
            from flask import request
            socket_id = request.sid

            user_info = self.connected_users.get(socket_id)
            if not user_info:
                emit(self.EVENT_ERROR, {'code': 'UNAUTHORIZED', 'message': 'Not authenticated'})
                return

            user_key = user_info['user_key']
            account_key = user_info['account_key']

            conversation_id = data.get('conversationId') or data.get('conversation_id')
            content = data.get('content') or data.get('message')
            message_type = data.get('type') or data.get('messageType', MessageType.TEXT)
            reply_to = data.get('replyTo') or data.get('reply_to')
            temp_id = data.get('tempId') or data.get('temp_id')
            media_url = data.get('mediaUrl') or data.get('media_url')
            mentions = data.get('mentions', [])

            if not conversation_id:
                emit(self.EVENT_ERROR, {'code': 'INVALID_DATA', 'message': 'conversationId required', 'tempId': temp_id})
                return

            if not content and not media_url:
                emit(self.EVENT_ERROR, {'code': 'INVALID_DATA', 'message': 'content required', 'tempId': temp_id})
                return

            repo = get_messaging_repository()
            if not repo or not repo.is_available():
                emit(self.EVENT_ERROR, {'code': 'SERVICE_UNAVAILABLE', 'tempId': temp_id})
                return

            try:
                conv = repo.get_conversation(conversation_id, user_key)
                if not conv:
                    emit(self.EVENT_ERROR, {'code': 'NOT_FOUND', 'message': 'Conversation not found', 'tempId': temp_id})
                    return

                message_id = generate_message_id()

                message = Message(
                    message_id=message_id,
                    conversation_id=conversation_id,
                    sender_key=user_key,
                    content=content,
                    message_type=message_type,
                    reply_to=reply_to,
                    media_url=media_url,
                    mentions=mentions,
                    account_key=account_key
                )

                stored_id = repo.send_message(message)
                if not stored_id:
                    emit(self.EVENT_ERROR, {'code': 'STORAGE_FAILED', 'tempId': temp_id})
                    return

                logger.debug(f"CHAT: msg sent id={message_id[:12]}...")

                now = datetime.utcnow()
                message_data = {
                    'messageId': message_id,
                    'conversationId': conversation_id,
                    'senderKey': user_key,
                    'content': content,
                    'type': message_type,
                    'status': MessageStatus.SENT,
                    'replyTo': reply_to,
                    'mediaUrl': media_url,
                    'mentions': mentions,
                    'createdAt': now.isoformat(),
                    'tempId': temp_id
                }

                user_repo = get_collection('users')
                if user_repo is not None:
                    sender = user_repo.find_one({'user_key': user_key})
                    if sender:
                        message_data['senderName'] = sender.get('name') or sender.get('username')
                        message_data['senderAvatar'] = sender.get('avatar_url')

                emit(self.EVENT_MESSAGE_SENT, message_data)

                participants = conv.get('participants', [])
                for participant in participants:
                    if participant != user_key:
                        self._emit_to_user(participant, self.EVENT_MESSAGE_NEW, message_data)

                        if participant in self.user_sockets:
                            repo.mark_delivered(message_id, participant)
                            emit(self.EVENT_MESSAGE_DELIVERED, {
                                'messageId': message_id,
                                'deliveredTo': participant,
                                'timestamp': now.isoformat()
                            })

            except Exception as e:
                logger.error(f"CHAT: send error: {e}")
                emit(self.EVENT_ERROR, {'code': 'SEND_FAILED', 'message': str(e), 'tempId': temp_id})

        @self.socketio.on('chat:read')
        def handle_mark_read(data):
            """Handle marking messages as read."""
            from flask import request
            socket_id = request.sid

            user_info = self.connected_users.get(socket_id)
            if not user_info:
                return

            user_key = user_info['user_key']
            conversation_id = data.get('conversationId') or data.get('conversation_id')
            message_id = data.get('messageId') or data.get('message_id')

            repo = get_messaging_repository()
            if not repo or not repo.is_available():
                return

            try:
                if conversation_id:
                    count = repo.mark_conversation_read(conversation_id, user_key)
                    logger.debug(f"CHAT: read conv={conversation_id[:12]}..., count={count}")

                    conv = repo.get_conversation(conversation_id)
                    if conv:
                        read_data = {
                            'conversationId': conversation_id,
                            'readBy': user_key,
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        for participant in conv.get('participants', []):
                            if participant != user_key:
                                self._emit_to_user(participant, self.EVENT_MESSAGE_READ, read_data)

                elif message_id:
                    repo.mark_read(message_id, user_key)

            except Exception as e:
                logger.error(f"CHAT: read error: {e}")

        @self.socketio.on('chat:typing')
        def handle_typing(data):
            """Handle typing indicator."""
            from flask import request
            socket_id = request.sid

            user_info = self.connected_users.get(socket_id)
            if not user_info:
                return

            user_key = user_info['user_key']
            conversation_id = data.get('conversationId') or data.get('conversation_id')
            is_typing = data.get('isTyping', True)

            if not conversation_id:
                return

            repo = get_messaging_repository()
            if not repo or not repo.is_available():
                return

            try:
                repo.set_user_typing(user_key, conversation_id, is_typing)

                conv = repo.get_conversation(conversation_id)
                if conv:
                    event = self.EVENT_TYPING_START if is_typing else self.EVENT_TYPING_STOP
                    typing_data = {
                        'conversationId': conversation_id,
                        'userKey': user_key,
                        'isTyping': is_typing
                    }
                    for participant in conv.get('participants', []):
                        if participant != user_key:
                            self._emit_to_user(participant, event, typing_data)

            except Exception as e:
                logger.error(f"CHAT: typing error: {e}")

        @self.socketio.on('chat:edit')
        def handle_edit_message(data):
            """Handle message edit."""
            from flask import request
            socket_id = request.sid

            user_info = self.connected_users.get(socket_id)
            if not user_info:
                emit(self.EVENT_ERROR, {'code': 'UNAUTHORIZED'})
                return

            user_key = user_info['user_key']
            message_id = data.get('messageId') or data.get('message_id')
            new_content = data.get('content')

            if not message_id or not new_content:
                emit(self.EVENT_ERROR, {'code': 'INVALID_DATA'})
                return

            repo = get_messaging_repository()
            if not repo or not repo.is_available():
                emit(self.EVENT_ERROR, {'code': 'SERVICE_UNAVAILABLE'})
                return

            try:
                success = repo.edit_message(message_id, user_key, new_content)

                if success:
                    msg = repo.get_message(message_id)
                    if msg:
                        edit_data = {
                            'messageId': message_id,
                            'content': new_content,
                            'editedAt': datetime.utcnow().isoformat()
                        }
                        emit(self.EVENT_MESSAGE_EDITED, edit_data)

                        conv = repo.get_conversation(msg.get('conversation_id'))
                        if conv:
                            for participant in conv.get('participants', []):
                                if participant != user_key:
                                    self._emit_to_user(participant, self.EVENT_MESSAGE_EDITED, edit_data)
                else:
                    emit(self.EVENT_ERROR, {'code': 'EDIT_FAILED'})

            except Exception as e:
                logger.error(f"CHAT: edit error: {e}")
                emit(self.EVENT_ERROR, {'code': 'EDIT_FAILED', 'message': str(e)})

        @self.socketio.on('chat:delete')
        def handle_delete_message(data):
            """Handle message delete."""
            from flask import request
            socket_id = request.sid

            user_info = self.connected_users.get(socket_id)
            if not user_info:
                emit(self.EVENT_ERROR, {'code': 'UNAUTHORIZED'})
                return

            user_key = user_info['user_key']
            message_id = data.get('messageId') or data.get('message_id')
            for_everyone = data.get('forEveryone', False)

            if not message_id:
                emit(self.EVENT_ERROR, {'code': 'INVALID_DATA'})
                return

            repo = get_messaging_repository()
            if not repo or not repo.is_available():
                emit(self.EVENT_ERROR, {'code': 'SERVICE_UNAVAILABLE'})
                return

            try:
                msg = repo.get_message(message_id)
                if not msg:
                    emit(self.EVENT_ERROR, {'code': 'NOT_FOUND'})
                    return

                success = repo.delete_message(message_id, user_key, for_everyone)

                if success:
                    delete_data = {
                        'messageId': message_id,
                        'deletedBy': user_key,
                        'forEveryone': for_everyone,
                        'deletedAt': datetime.utcnow().isoformat()
                    }
                    emit(self.EVENT_MESSAGE_DELETED, delete_data)

                    if for_everyone:
                        conv = repo.get_conversation(msg.get('conversation_id'))
                        if conv:
                            for participant in conv.get('participants', []):
                                if participant != user_key:
                                    self._emit_to_user(participant, self.EVENT_MESSAGE_DELETED, delete_data)
                else:
                    emit(self.EVENT_ERROR, {'code': 'DELETE_FAILED'})

            except Exception as e:
                logger.error(f"CHAT: delete error: {e}")
                emit(self.EVENT_ERROR, {'code': 'DELETE_FAILED', 'message': str(e)})

        # =====================================================================
        # Conversation Events
        # =====================================================================

        @self.socketio.on('chat:conversation:create')
        def handle_create_conversation(data):
            """Handle creating a new conversation."""
            from flask import request
            socket_id = request.sid

            user_info = self.connected_users.get(socket_id)
            if not user_info:
                emit(self.EVENT_ERROR, {'code': 'UNAUTHORIZED'})
                return

            user_key = user_info['user_key']
            account_key = user_info['account_key']

            conv_type = data.get('type', 'direct')
            participants = data.get('participants', [])
            name = data.get('name')

            if not participants:
                emit(self.EVENT_ERROR, {'code': 'INVALID_DATA', 'message': 'participants required'})
                return

            if user_key not in participants:
                participants = [user_key] + participants

            repo = get_messaging_repository()
            if not repo or not repo.is_available():
                emit(self.EVENT_ERROR, {'code': 'SERVICE_UNAVAILABLE'})
                return

            try:
                conversation_id = generate_conversation_id()

                conversation = Conversation(
                    conversation_id=conversation_id,
                    conversation_type=ConversationType.DIRECT if conv_type == 'direct' else ConversationType.GROUP,
                    participants=participants,
                    name=name,
                    account_key=account_key,
                    created_by=user_key
                )

                created_id = repo.create_conversation(conversation)
                logger.debug(f"CHAT: conv created id={created_id[:12]}...")

                conv_data = {
                    'conversationId': created_id,
                    'type': conv_type,
                    'participants': participants,
                    'name': name,
                    'createdBy': user_key,
                    'createdAt': datetime.utcnow().isoformat()
                }

                emit(self.EVENT_CONVERSATION_CREATED, conv_data)

                for participant in participants:
                    if participant != user_key:
                        self._emit_to_user(participant, self.EVENT_CONVERSATION_CREATED, conv_data)

            except Exception as e:
                logger.error(f"CHAT: create conv error: {e}")
                emit(self.EVENT_ERROR, {'code': 'CREATE_FAILED', 'message': str(e)})

        @self.socketio.on('chat:conversation:join')
        def handle_join_conversation(data):
            """Handle joining a conversation room."""
            from flask import request
            socket_id = request.sid

            user_info = self.connected_users.get(socket_id)
            if not user_info:
                return

            conversation_id = data.get('conversationId') or data.get('conversation_id')
            if not conversation_id:
                return

            user_key = user_info['user_key']

            repo = get_messaging_repository()
            if repo and repo.is_available():
                conv = repo.get_conversation(conversation_id, user_key)
                if conv and user_key in conv.get('participants', []):
                    join_room(f"conv:{conversation_id}")
                    emit('chat:conversation:joined', {'conversationId': conversation_id})

        @self.socketio.on('chat:conversation:leave')
        def handle_leave_conversation(data):
            """Handle leaving a conversation room."""
            conversation_id = data.get('conversationId') or data.get('conversation_id')
            if conversation_id:
                leave_room(f"conv:{conversation_id}")

        @self.socketio.on('chat:conversation:clear')
        def handle_clear_conversation(data):
            """Handle clearing conversation messages."""
            from flask import request
            socket_id = request.sid

            user_info = self.connected_users.get(socket_id)
            if not user_info:
                emit(self.EVENT_ERROR, {'code': 'UNAUTHORIZED'})
                return

            user_key = user_info['user_key']
            conversation_id = data.get('conversationId') or data.get('conversation_id')
            for_everyone = data.get('forEveryone', False)

            if not conversation_id:
                emit(self.EVENT_ERROR, {'code': 'INVALID_DATA'})
                return

            repo = get_messaging_repository()
            if not repo or not repo.is_available():
                emit(self.EVENT_ERROR, {'code': 'SERVICE_UNAVAILABLE'})
                return

            try:
                count = repo.clear_conversation(conversation_id, user_key, for_everyone)
                logger.debug(f"CHAT: conv cleared id={conversation_id[:12]}..., count={count}")

                clear_data = {
                    'conversationId': conversation_id,
                    'clearedBy': user_key,
                    'forEveryone': for_everyone,
                    'messagesCleared': count
                }

                emit('chat:conversation:cleared', clear_data)

                if for_everyone:
                    conv = repo.get_conversation(conversation_id)
                    if conv:
                        for participant in conv.get('participants', []):
                            if participant != user_key:
                                self._emit_to_user(participant, 'chat:conversation:cleared', clear_data)

            except Exception as e:
                logger.error(f"CHAT: clear error: {e}")
                emit(self.EVENT_ERROR, {'code': 'CLEAR_FAILED', 'message': str(e)})

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _emit_to_user(self, user_key: str, event: str, data: Dict):
        """Emit event to all sockets of a user."""
        sockets = self.user_sockets.get(user_key, [])
        for socket_id in sockets:
            try:
                self.socketio.emit(event, data, room=socket_id)
            except Exception as e:
                logger.debug(f"CHAT: emit failed to {socket_id}: {e}")

    def on_user_connected(self, user_key: str, account_key: str, socket_id: str):
        """Handle user connection - join conversation rooms."""
        repo = get_messaging_repository()
        if not repo or not repo.is_available():
            return

        try:
            conversation_ids = repo.get_user_conversation_ids(user_key)
            for conv_id in conversation_ids[:50]:
                join_room(f"conv:{conv_id}", sid=socket_id)

            repo.set_user_online(user_key, socket_id)
        except Exception as e:
            logger.error(f"CHAT: connect setup error: {e}")

    def on_user_disconnected(self, user_key: str, account_key: str):
        """Handle user disconnection."""
        repo = get_messaging_repository()
        if repo and repo.is_available():
            try:
                repo.set_user_offline(user_key)
            except Exception as e:
                logger.error(f"CHAT: disconnect error: {e}")


# Module-level singleton
_chat_handler: Optional[ChatHandler] = None


def init_chat_handler(socketio, connected_users: Dict, user_sockets: Dict) -> ChatHandler:
    """Initialize chat handler singleton."""
    global _chat_handler
    if _chat_handler is None:
        _chat_handler = ChatHandler(socketio, connected_users, user_sockets)
        _chat_handler.register_handlers()
    return _chat_handler


def get_chat_handler() -> Optional[ChatHandler]:
    """Get chat handler singleton."""
    return _chat_handler

