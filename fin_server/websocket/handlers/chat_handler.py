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
        print("CHAT_HANDLER: Registering WebSocket chat event handlers")

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

            print("=" * 50)
            print(f"CHAT_HANDLER: 'chat:send' received from socket {socket_id}")
            print(f"CHAT_HANDLER: Data: {data}")

            user_info = self.connected_users.get(socket_id)

            if not user_info:
                print(f"CHAT_HANDLER: Unauthorized - no user info for socket {socket_id}")
                emit(self.EVENT_ERROR, {
                    'code': 'UNAUTHORIZED',
                    'message': 'Not authenticated'
                })
                return

            user_key = user_info['user_key']
            account_key = user_info['account_key']
            print(f"CHAT_HANDLER: Sender: user_key={user_key}, account_key={account_key}")

            # Extract data
            conversation_id = data.get('conversationId') or data.get('conversation_id')
            content = data.get('content') or data.get('message')
            message_type = data.get('type') or data.get('messageType', MessageType.TEXT)
            reply_to = data.get('replyTo') or data.get('reply_to')
            temp_id = data.get('tempId') or data.get('temp_id')  # Client's temporary ID
            media_url = data.get('mediaUrl') or data.get('media_url')
            mentions = data.get('mentions', [])

            print(f"CHAT_HANDLER: Parsed - conv={conversation_id}, content_len={len(content) if content else 0}, type={message_type}")

            # Validate required fields
            if not conversation_id:
                print("CHAT_HANDLER: ERROR - Missing conversationId")
                emit(self.EVENT_ERROR, {
                    'code': 'INVALID_DATA',
                    'message': 'conversationId is required',
                    'tempId': temp_id
                })
                return

            if not content and not media_url:
                print("CHAT_HANDLER: ERROR - Missing content and mediaUrl")
                emit(self.EVENT_ERROR, {
                    'code': 'INVALID_DATA',
                    'message': 'content or mediaUrl is required',
                    'tempId': temp_id
                })
                return

            repo = get_messaging_repository()
            print(f"CHAT_HANDLER: Repo available: {repo is not None and repo.is_available()}")
            if not repo or not repo.is_available():
                print("CHAT_HANDLER: ERROR - Chat service unavailable")
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
                    print(f"CHAT_HANDLER: ERROR - Conversation {conversation_id} not found or access denied")
                    emit(self.EVENT_ERROR, {
                        'code': 'NOT_FOUND',
                        'message': 'Conversation not found or access denied',
                        'tempId': temp_id
                    })
                    return

                print(f"CHAT_HANDLER: Conversation found, participants: {conv.get('participants', [])}")

                # Generate unique message ID
                message_id = generate_message_id()
                print(f"CHAT_HANDLER: Generated message_id: {message_id}")

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
                print("CHAT_HANDLER: Storing message in database...")
                stored_id = repo.send_message(message)

                if not stored_id:
                    print("CHAT_HANDLER: ERROR - Failed to store message in database")
                    emit(self.EVENT_ERROR, {
                        'code': 'STORAGE_FAILED',
                        'message': 'Failed to store message',
                        'tempId': temp_id
                    })
                    return

                print(f"CHAT_HANDLER: Message stored successfully, stored_id: {stored_id}")

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
                print(f"CHAT_HANDLER: Sending '{self.EVENT_MESSAGE_SENT}' to sender")
                emit(self.EVENT_MESSAGE_SENT, message_data)

                # Broadcast to other participants
                participants = conv.get('participants', [])
                print(f"CHAT_HANDLER: Broadcasting to {len(participants) - 1} other participants")
                for participant in participants:
                    if participant != user_key:
                        print(f"CHAT_HANDLER: Sending message to participant {participant}")
                        self._emit_to_user(participant, self.EVENT_MESSAGE_NEW, message_data)

                        # Mark as delivered if user is online
                        if participant in self.user_sockets:
                            print(f"CHAT_HANDLER: Participant {participant} is online, marking delivered")
                            repo.mark_delivered(message_id, participant)
                            # Notify sender of delivery
                            emit(self.EVENT_MESSAGE_DELIVERED, {
                                'messageId': message_id,
                                'deliveredTo': participant,
                                'timestamp': now.isoformat()
                            })
                        else:
                            print(f"CHAT_HANDLER: Participant {participant} is OFFLINE")

                print(f"CHAT_HANDLER: ✅ Message {message_id} sent SUCCESSFULLY by {user_key}")
                print("=" * 50)

            except Exception as e:
                print(f"CHAT_HANDLER: ERROR sending message: {e}")
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
            logger.info(f"CHAT_HANDLER: 'chat:read' received - data={data}")

            user_info = self.connected_users.get(socket_id)

            if not user_info:
                logger.warning("CHAT_HANDLER: chat:read - user not authenticated")
                return

            user_key = user_info['user_key']
            conversation_id = data.get('conversationId') or data.get('conversation_id')
            message_id = data.get('messageId') or data.get('message_id')

            repo = get_messaging_repository()
            if not repo or not repo.is_available():
                logger.error("CHAT_HANDLER: chat:read - repo not available")
                return

            try:
                if conversation_id:
                    # Mark all messages in conversation as read
                    logger.info(f"CHAT_HANDLER: Marking all messages in conversation {conversation_id} as read")
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

            print("=" * 60)
            print("CHAT_HANDLER: chat:conversation:create received!")
            print(f"CHAT_HANDLER: Data: {data}")

            socket_id = request.sid
            user_info = self.connected_users.get(socket_id)

            if not user_info:
                print("CHAT_HANDLER: User not authenticated")
                emit(self.EVENT_ERROR, {'code': 'UNAUTHORIZED', 'message': 'Not authenticated'})
                return

            user_key = user_info['user_key']
            account_key = user_info['account_key']
            print(f"CHAT_HANDLER: Creator: user_key={user_key}, account_key={account_key}")

            conv_type = data.get('type', 'direct')
            participants = data.get('participants', [])
            name = data.get('name')

            print(f"CHAT_HANDLER: type={conv_type}, participants={participants}, name={name}")

            # Ensure creator is in participants
            if user_key not in participants:
                participants.insert(0, user_key)
                print(f"CHAT_HANDLER: Added creator to participants: {participants}")

            if conv_type == 'direct' and len(participants) != 2:
                print(f"CHAT_HANDLER: ERROR - Direct conv needs 2 participants, got {len(participants)}")
                emit(self.EVENT_ERROR, {
                    'code': 'INVALID_DATA',
                    'message': 'Direct conversation requires exactly 2 participants'
                })
                return

            repo = get_messaging_repository()
            print(f"CHAT_HANDLER: Repo available: {repo is not None and repo.is_available()}")

            if not repo or not repo.is_available():
                print("CHAT_HANDLER: ERROR - Messaging repository not available")
                emit(self.EVENT_ERROR, {'code': 'SERVICE_UNAVAILABLE', 'message': 'Service unavailable'})
                return

            try:
                conv_id_generated = generate_conversation_id()
                print(f"CHAT_HANDLER: Generated conversation_id: {conv_id_generated}")

                conversation = Conversation(
                    conversation_id=conv_id_generated,
                    conversation_type=ConversationType.DIRECT if conv_type == 'direct' else ConversationType.GROUP,
                    participants=participants,
                    name=name,
                    created_by=user_key,
                    account_key=account_key,
                    admins=[user_key] if conv_type == 'group' else []
                )

                print(f"CHAT_HANDLER: Calling repo.create_conversation()...")
                conv_id = repo.create_conversation(conversation)
                print(f"CHAT_HANDLER: ✅ Conversation created with ID: {conv_id}")

                conv_data = {
                    'conversationId': conv_id,
                    'type': conv_type,
                    'participants': participants,
                    'name': name,
                    'createdBy': user_key,
                    'createdAt': datetime.utcnow().isoformat()
                }

                # Confirm to creator
                print(f"CHAT_HANDLER: Emitting {self.EVENT_CONVERSATION_CREATED} to creator")
                emit(self.EVENT_CONVERSATION_CREATED, conv_data)

                # Notify other participants
                for participant in participants:
                    if participant != user_key:
                        print(f"CHAT_HANDLER: Notifying participant {participant}")
                        self._emit_to_user(participant, self.EVENT_CONVERSATION_CREATED, conv_data)

                        # Join them to the conversation room
                        for sid in self.user_sockets.get(participant, []):
                            try:
                                join_room(f"conv:{conv_id}", sid=sid, namespace='/')
                                print(f"CHAT_HANDLER: Joined socket {sid} to room conv:{conv_id}")
                            except Exception as join_err:
                                print(f"CHAT_HANDLER: Could not join socket {sid} to room (stale?): {join_err}")

                # Join creator to room
                try:
                    join_room(f"conv:{conv_id}")
                    print(f"CHAT_HANDLER: Creator joined room conv:{conv_id}")
                except Exception as join_err:
                    print(f"CHAT_HANDLER: Could not join creator to room: {join_err}")

                print(f"CHAT_HANDLER: ✅ Conversation {conv_id} created successfully by {user_key}")
                print("=" * 60)

            except Exception as e:
                print(f"CHAT_HANDLER: ERROR creating conversation - {e}")
                import traceback
                traceback.print_exc()
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
        print(f"CHAT_HANDLER: _emit_to_user - user={user_key}, event={event}, sockets={len(sockets)}")

        if not sockets:
            print(f"CHAT_HANDLER: No sockets found for user {user_key}")
            return

        stale_sockets = []
        for sid in sockets:
            try:
                self.socketio.emit(event, data, room=sid)
                print(f"CHAT_HANDLER: Emitted '{event}' to socket {sid}")
            except Exception as e:
                print(f"CHAT_HANDLER: ERROR emitting to socket {sid}: {e} (marking as stale)")
                stale_sockets.append(sid)

        # Clean up stale sockets
        if stale_sockets:
            print(f"CHAT_HANDLER: Cleaning up {len(stale_sockets)} stale sockets for user {user_key}")
            for stale_sid in stale_sockets:
                if stale_sid in self.user_sockets.get(user_key, []):
                    self.user_sockets[user_key].remove(stale_sid)
                if stale_sid in self.connected_users:
                    del self.connected_users[stale_sid]

    def on_user_connected(self, user_key: str, account_key: str, socket_id: str):
        """Called when a user connects. Join their conversation rooms."""
        print(f"CHAT_HANDLER: on_user_connected - user={user_key}, socket={socket_id}")

        repo = get_messaging_repository()
        if repo and repo.is_available():
            try:
                # Get user's conversations and join rooms
                conversations = repo.get_user_conversations(user_key, account_key)
                print(f"CHAT_HANDLER: User has {len(conversations)} conversations")

                for conv in conversations:
                    conv_id = conv.get('conversation_id') or str(conv.get('_id'))
                    join_room(f"conv:{conv_id}", sid=socket_id, namespace='/')
                    print(f"CHAT_HANDLER: Joined room conv:{conv_id}")

                # Update presence
                device_info = {}
                repo.set_user_online(user_key, socket_id, device_info)
                print(f"CHAT_HANDLER: User {user_key} presence set to ONLINE")

                # Broadcast online status
                self._broadcast_presence(user_key, 'online', account_key)

            except Exception as e:
                print(f"CHAT_HANDLER: ERROR on user connected: {e}")
        else:
            print("CHAT_HANDLER: on_user_connected - repo not available")

    def on_user_disconnected(self, user_key: str, account_key: str):
        """Called when a user disconnects (all devices)."""
        print(f"CHAT_HANDLER: on_user_disconnected - user={user_key}")

        repo = get_messaging_repository()
        if repo and repo.is_available():
            try:
                repo.set_user_offline(user_key)
                print(f"CHAT_HANDLER: User {user_key} presence set to OFFLINE")
                self._broadcast_presence(user_key, 'offline', account_key)
            except Exception as e:
                print(f"CHAT_HANDLER: ERROR on user disconnected: {e}")

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
            print(f"CHAT_HANDLER: ERROR broadcasting presence: {e}")


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
    print("CHAT_HANDLER: Chat handler initialized")
    return _chat_handler

