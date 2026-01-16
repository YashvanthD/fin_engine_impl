"""WebSocket Chat Handler.

This module handles all real-time chat operations via WebSocket.
REST API is only used for:
- Initial message history loading (GET /api/chat/conversations/{id}/messages)
- Conversation listing (GET /api/chat/conversations)

All real-time operations go through WebSocket:
- Sending messages
- Receiving messages
- Typing indicators
- Read receipts
- Message edits/deletes
- Presence updates

Data Consistency:
- Messages are stored in MongoDB before being broadcast
- Each message has a unique message_id for deduplication
- Client receives confirmation after successful storage
- Failed sends are reported to the client
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
        """Initialize chat handler.

        Args:
            socketio: Flask-SocketIO instance
            connected_users: Dict mapping socket_id -> user info
            user_sockets: Dict mapping user_key -> [socket_ids]
        """
        self.socketio = socketio
        self.connected_users = connected_users
        self.user_sockets = user_sockets

    def register_handlers(self):
        """Register all chat WebSocket event handlers."""

        # =====================================================================
        # Message Events
        # =====================================================================

        @self.socketio.on('chat:send')
        def handle_send_message(data):
            """Handle sending a new message.

            Data:
                conversationId: str - Target conversation
                content: str - Message content
                type: str - Message type (text, image, file, etc.)
                replyTo: str - Optional message ID being replied to
                tempId: str - Client-side temporary ID for optimistic updates

            Response Events:
                - chat:message:sent (to sender) - Confirmation with server message_id
                - chat:message (to other participants) - New message notification
                - chat:error (on failure)
            """
            from flask import request
            socket_id = request.sid
            user_info = self.connected_users.get(socket_id)

            if not user_info:
                emit(self.EVENT_ERROR, {
                    'code': 'UNAUTHORIZED',
                    'message': 'Not authenticated'
                })
                return

            user_key = user_info['user_key']
            account_key = user_info['account_key']

            # Extract data
            conversation_id = data.get('conversationId') or data.get('conversation_id')
            content = data.get('content') or data.get('message')
            message_type = data.get('type') or data.get('messageType', MessageType.TEXT)
            reply_to = data.get('replyTo') or data.get('reply_to')
            temp_id = data.get('tempId') or data.get('temp_id')  # Client's temporary ID
            media_url = data.get('mediaUrl') or data.get('media_url')
            mentions = data.get('mentions', [])

            # Validate required fields
            if not conversation_id:
                emit(self.EVENT_ERROR, {
                    'code': 'INVALID_DATA',
                    'message': 'conversationId is required',
                    'tempId': temp_id
                })
                return

            if not content and not media_url:
                emit(self.EVENT_ERROR, {
                    'code': 'INVALID_DATA',
                    'message': 'content or mediaUrl is required',
                    'tempId': temp_id
                })
                return

            repo = get_messaging_repository()
            if not repo or not repo.is_available():
                emit(self.EVENT_ERROR, {
                    'code': 'SERVICE_UNAVAILABLE',
                    'message': 'Chat service temporarily unavailable',
                    'tempId': temp_id
                })
                return

            try:
                # Verify user is participant in conversation
                conv = repo.get_conversation(conversation_id, user_key)
                if not conv:
                    emit(self.EVENT_ERROR, {
                        'code': 'NOT_FOUND',
                        'message': 'Conversation not found or access denied',
                        'tempId': temp_id
                    })
                    return

                # Generate unique message ID
                message_id = generate_message_id()

                # Create message object
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

                # Store message in database FIRST (data consistency)
                stored_id = repo.send_message(message)

                if not stored_id:
                    emit(self.EVENT_ERROR, {
                        'code': 'STORAGE_FAILED',
                        'message': 'Failed to store message',
                        'tempId': temp_id
                    })
                    return

                # Build message data for broadcast
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
                    'tempId': temp_id  # Include temp_id for client-side matching
                }

                # Get sender info for display
                user_repo = get_collection('users')
                if user_repo is not None:
                    sender = user_repo.find_one({'user_key': user_key})
                    if sender:
                        message_data['senderName'] = sender.get('name') or sender.get('username')
                        message_data['senderAvatar'] = sender.get('avatar_url')

                # Send confirmation to sender
                emit(self.EVENT_MESSAGE_SENT, message_data)

                # Broadcast to other participants
                participants = conv.get('participants', [])
                for participant in participants:
                    if participant != user_key:
                        self._emit_to_user(participant, self.EVENT_MESSAGE_NEW, message_data)

                        # Mark as delivered if user is online
                        if participant in self.user_sockets:
                            repo.mark_delivered(message_id, participant)
                            # Notify sender of delivery
                            emit(self.EVENT_MESSAGE_DELIVERED, {
                                'messageId': message_id,
                                'deliveredTo': participant,
                                'timestamp': now.isoformat()
                            })

                logger.info(f"Message {message_id} sent by {user_key} in conversation {conversation_id}")

            except Exception as e:
                logger.exception(f"Error sending message: {e}")
                emit(self.EVENT_ERROR, {
                    'code': 'SEND_FAILED',
                    'message': str(e),
                    'tempId': temp_id
                })

        @self.socketio.on('chat:read')
        def handle_mark_read(data):
            """Handle marking messages as read.

            Data:
                conversationId: str - Mark all messages in conversation as read
                messageId: str - Mark specific message as read (optional)
            """
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
                    # Mark all messages in conversation as read
                    count = repo.mark_conversation_read(conversation_id, user_key)

                    # Notify other participants
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
                    # Mark specific message as read
                    repo.mark_read(message_id, user_key)
                    msg = repo.get_message(message_id)
                    if msg:
                        read_data = {
                            'messageId': message_id,
                            'readBy': user_key,
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        # Notify sender
                        sender_key = msg.get('sender_key')
                        if sender_key and sender_key != user_key:
                            self._emit_to_user(sender_key, self.EVENT_MESSAGE_READ, read_data)

            except Exception as e:
                logger.error(f"Error marking read: {e}")

        @self.socketio.on('chat:delivered')
        def handle_mark_delivered(data):
            """Handle marking messages as delivered.

            Data:
                messageId: str - Message to mark as delivered
            """
            from flask import request
            socket_id = request.sid
            user_info = self.connected_users.get(socket_id)

            if not user_info:
                return

            message_id = data.get('messageId') or data.get('message_id')
            if not message_id:
                return

            user_key = user_info['user_key']
            repo = get_messaging_repository()

            if repo and repo.is_available():
                try:
                    repo.mark_delivered(message_id, user_key)
                    msg = repo.get_message(message_id)
                    if msg:
                        sender_key = msg.get('sender_key')
                        if sender_key and sender_key != user_key:
                            self._emit_to_user(sender_key, self.EVENT_MESSAGE_DELIVERED, {
                                'messageId': message_id,
                                'deliveredTo': user_key,
                                'timestamp': datetime.utcnow().isoformat()
                            })
                except Exception as e:
                    logger.error(f"Error marking delivered: {e}")

        # =====================================================================
        # Typing Indicators
        # =====================================================================

        @self.socketio.on('chat:typing')
        def handle_typing(data):
            """Handle typing indicator.

            Data:
                conversationId: str - Conversation where typing
                isTyping: bool - True if started typing, False if stopped
            """
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
            if not repo:
                return

            try:
                conv = repo.get_conversation(conversation_id, user_key)
                if not conv:
                    return

                # Update presence
                repo.set_user_typing(user_key, conversation_id, is_typing)

                # Broadcast to other participants
                typing_data = {
                    'conversationId': conversation_id,
                    'userKey': user_key,
                    'isTyping': is_typing,
                    'timestamp': datetime.utcnow().isoformat()
                }

                event = self.EVENT_TYPING_START if is_typing else self.EVENT_TYPING_STOP

                for participant in conv.get('participants', []):
                    if participant != user_key:
                        self._emit_to_user(participant, event, typing_data)

            except Exception as e:
                logger.error(f"Error handling typing: {e}")

        # =====================================================================
        # Message Edit/Delete
        # =====================================================================

        @self.socketio.on('chat:edit')
        def handle_edit_message(data):
            """Handle editing a message.

            Data:
                messageId: str - Message to edit
                content: str - New content
            """
            from flask import request
            socket_id = request.sid
            user_info = self.connected_users.get(socket_id)

            if not user_info:
                emit(self.EVENT_ERROR, {'code': 'UNAUTHORIZED', 'message': 'Not authenticated'})
                return

            message_id = data.get('messageId') or data.get('message_id')
            new_content = data.get('content')

            if not message_id or not new_content:
                emit(self.EVENT_ERROR, {'code': 'INVALID_DATA', 'message': 'messageId and content required'})
                return

            user_key = user_info['user_key']
            repo = get_messaging_repository()

            if not repo or not repo.is_available():
                emit(self.EVENT_ERROR, {'code': 'SERVICE_UNAVAILABLE', 'message': 'Service unavailable'})
                return

            try:
                # Edit in database first
                success = repo.edit_message(message_id, user_key, new_content)

                if not success:
                    emit(self.EVENT_ERROR, {'code': 'EDIT_FAILED', 'message': 'Cannot edit message'})
                    return

                msg = repo.get_message(message_id)
                conversation_id = msg.get('conversation_id')

                edit_data = {
                    'messageId': message_id,
                    'content': new_content,
                    'editedAt': datetime.utcnow().isoformat()
                }

                # Confirm to sender
                emit(self.EVENT_MESSAGE_EDITED, edit_data)

                # Broadcast to conversation
                conv = repo.get_conversation(conversation_id)
                if conv:
                    for participant in conv.get('participants', []):
                        if participant != user_key:
                            self._emit_to_user(participant, self.EVENT_MESSAGE_EDITED, edit_data)

                logger.info(f"Message {message_id} edited by {user_key}")

            except Exception as e:
                logger.exception(f"Error editing message: {e}")
                emit(self.EVENT_ERROR, {'code': 'EDIT_FAILED', 'message': str(e)})

        @self.socketio.on('chat:delete')
        def handle_delete_message(data):
            """Handle deleting a message.

            Data:
                messageId: str - Message to delete
                forEveryone: bool - Delete for all participants (default: false)
            """
            from flask import request
            socket_id = request.sid
            user_info = self.connected_users.get(socket_id)

            if not user_info:
                emit(self.EVENT_ERROR, {'code': 'UNAUTHORIZED', 'message': 'Not authenticated'})
                return

            message_id = data.get('messageId') or data.get('message_id')
            for_everyone = data.get('forEveryone', False)

            if not message_id:
                emit(self.EVENT_ERROR, {'code': 'INVALID_DATA', 'message': 'messageId required'})
                return

            user_key = user_info['user_key']
            repo = get_messaging_repository()

            if not repo or not repo.is_available():
                emit(self.EVENT_ERROR, {'code': 'SERVICE_UNAVAILABLE', 'message': 'Service unavailable'})
                return

            try:
                msg = repo.get_message(message_id)
                if not msg:
                    emit(self.EVENT_ERROR, {'code': 'NOT_FOUND', 'message': 'Message not found'})
                    return

                conversation_id = msg.get('conversation_id')

                # Delete in database first
                success = repo.delete_message(message_id, user_key, for_everyone)

                if not success:
                    emit(self.EVENT_ERROR, {'code': 'DELETE_FAILED', 'message': 'Cannot delete message'})
                    return

                delete_data = {
                    'messageId': message_id,
                    'deletedAt': datetime.utcnow().isoformat(),
                    'forEveryone': for_everyone
                }

                # Confirm to sender
                emit(self.EVENT_MESSAGE_DELETED, delete_data)

                # Broadcast to conversation if deleted for everyone
                if for_everyone:
                    conv = repo.get_conversation(conversation_id)
                    if conv:
                        for participant in conv.get('participants', []):
                            if participant != user_key:
                                self._emit_to_user(participant, self.EVENT_MESSAGE_DELETED, delete_data)

                logger.info(f"Message {message_id} deleted by {user_key} (forEveryone: {for_everyone})")

            except Exception as e:
                logger.exception(f"Error deleting message: {e}")
                emit(self.EVENT_ERROR, {'code': 'DELETE_FAILED', 'message': str(e)})

        # =====================================================================
        # Conversation Management
        # =====================================================================

        @self.socketio.on('chat:conversation:create')
        def handle_create_conversation(data):
            """Handle creating a new conversation.

            Data:
                type: str - 'direct' or 'group'
                participants: list - User keys to include
                name: str - Group name (for groups)
            """
            from flask import request
            socket_id = request.sid
            user_info = self.connected_users.get(socket_id)

            if not user_info:
                emit(self.EVENT_ERROR, {'code': 'UNAUTHORIZED', 'message': 'Not authenticated'})
                return

            user_key = user_info['user_key']
            account_key = user_info['account_key']

            conv_type = data.get('type', 'direct')
            participants = data.get('participants', [])
            name = data.get('name')

            # Ensure creator is in participants
            if user_key not in participants:
                participants.insert(0, user_key)

            if conv_type == 'direct' and len(participants) != 2:
                emit(self.EVENT_ERROR, {
                    'code': 'INVALID_DATA',
                    'message': 'Direct conversation requires exactly 2 participants'
                })
                return

            repo = get_messaging_repository()
            if not repo or not repo.is_available():
                emit(self.EVENT_ERROR, {'code': 'SERVICE_UNAVAILABLE', 'message': 'Service unavailable'})
                return

            try:
                conversation = Conversation(
                    conversation_id=generate_conversation_id(),
                    conversation_type=ConversationType.DIRECT if conv_type == 'direct' else ConversationType.GROUP,
                    participants=participants,
                    name=name,
                    created_by=user_key,
                    account_key=account_key,
                    admins=[user_key] if conv_type == 'group' else []
                )

                conv_id = repo.create_conversation(conversation)

                conv_data = {
                    'conversationId': conv_id,
                    'type': conv_type,
                    'participants': participants,
                    'name': name,
                    'createdBy': user_key,
                    'createdAt': datetime.utcnow().isoformat()
                }

                # Confirm to creator
                emit(self.EVENT_CONVERSATION_CREATED, conv_data)

                # Notify other participants
                for participant in participants:
                    if participant != user_key:
                        self._emit_to_user(participant, self.EVENT_CONVERSATION_CREATED, conv_data)

                        # Join them to the conversation room
                        for sid in self.user_sockets.get(participant, []):
                            join_room(f"conv:{conv_id}", sid=sid, namespace='/')

                # Join creator to room
                join_room(f"conv:{conv_id}")

                logger.info(f"Conversation {conv_id} created by {user_key}")

            except Exception as e:
                logger.exception(f"Error creating conversation: {e}")
                emit(self.EVENT_ERROR, {'code': 'CREATE_FAILED', 'message': str(e)})

        @self.socketio.on('chat:conversation:join')
        def handle_join_conversation(data):
            """Join a conversation room to receive messages."""
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
            """Leave a conversation room (stop receiving messages)."""
            conversation_id = data.get('conversationId') or data.get('conversation_id')
            if conversation_id:
                leave_room(f"conv:{conversation_id}")
                emit('chat:conversation:left', {'conversationId': conversation_id})

    def _emit_to_user(self, user_key: str, event: str, data: Any):
        """Emit event to all connected devices of a user."""
        sockets = self.user_sockets.get(user_key, [])
        for sid in sockets:
            self.socketio.emit(event, data, room=sid)

    def on_user_connected(self, user_key: str, account_key: str, socket_id: str):
        """Called when a user connects. Join their conversation rooms."""
        repo = get_messaging_repository()
        if repo and repo.is_available():
            try:
                # Get user's conversations and join rooms
                conversations = repo.get_user_conversations(user_key, account_key)
                for conv in conversations:
                    conv_id = conv.get('conversation_id') or str(conv.get('_id'))
                    join_room(f"conv:{conv_id}", sid=socket_id, namespace='/')

                # Update presence
                device_info = {}
                repo.set_user_online(user_key, socket_id, device_info)

                # Broadcast online status
                self._broadcast_presence(user_key, 'online', account_key)

            except Exception as e:
                logger.error(f"Error on user connected: {e}")

    def on_user_disconnected(self, user_key: str, account_key: str):
        """Called when a user disconnects (all devices)."""
        repo = get_messaging_repository()
        if repo and repo.is_available():
            try:
                repo.set_user_offline(user_key)
                self._broadcast_presence(user_key, 'offline', account_key)
            except Exception as e:
                logger.error(f"Error on user disconnected: {e}")

    def _broadcast_presence(self, user_key: str, status: str, account_key: str):
        """Broadcast user presence to their contacts."""
        repo = get_messaging_repository()
        if not repo:
            return

        try:
            # Get all conversations user is part of
            conversations = repo.get_user_conversations(user_key, account_key, limit=100)

            # Collect unique contacts
            contacts = set()
            for conv in conversations:
                for participant in conv.get('participants', []):
                    if participant != user_key:
                        contacts.add(participant)

            # Broadcast to all contacts
            presence_data = {
                'userKey': user_key,
                'status': status,
                'timestamp': datetime.utcnow().isoformat()
            }

            for contact in contacts:
                self._emit_to_user(contact, self.EVENT_PRESENCE_UPDATE, presence_data)

        except Exception as e:
            logger.error(f"Error broadcasting presence: {e}")


# Singleton instance
_chat_handler: Optional[ChatHandler] = None


def get_chat_handler() -> Optional[ChatHandler]:
    """Get chat handler instance."""
    return _chat_handler


def init_chat_handler(socketio, connected_users: Dict, user_sockets: Dict) -> ChatHandler:
    """Initialize chat handler with socketio instance."""
    global _chat_handler
    _chat_handler = ChatHandler(socketio, connected_users, user_sockets)
    _chat_handler.register_handlers()
    logger.info("Chat handler initialized")
    return _chat_handler

