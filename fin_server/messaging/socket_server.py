import socketio
from flask import Flask
from fin_server.security.authentication import AuthSecurity
from fin_server.exception.UnauthorizedError import UnauthorizedError
import logging
from pymongo import MongoClient
from fin_server.repository.message_repository import MessageRepository
from fin_server.repository.notification_repository import NotificationRepository

sio = socketio.Server(async_mode='threading', cors_allowed_origins='*')
app = Flask(__name__)

# Setup MongoDB connection
mongo_client = MongoClient('mongodb://localhost:27017/')
db = mongo_client['fin_db']
message_repository = MessageRepository(db)
notification_repository = NotificationRepository(db)

connected_users = {}  # user_key: sid

@sio.event
def connect(sid, environ):
    token = environ.get('HTTP_AUTHORIZATION')
    if not token or not token.startswith('Bearer '):
        return False
    token = token.split(' ', 1)[1]
    try:
        payload = AuthSecurity.decode_token(token)
        user_key = payload.get('user_key')
        connected_users[user_key] = sid
        sio.emit('user_connected', {'user_key': user_key}, room=sid)
        logging.info(f"User {user_key} connected via socket {sid}")
        # Deliver undelivered messages
        undelivered_msgs = message_repository.get_undelivered_messages(user_key)
        for msg in undelivered_msgs:
            sio.emit('receive_message', {'from_user_key': msg['from_user_key'], 'message': msg['message']}, room=sid)
            message_repository.mark_as_delivered(msg['_id'])
        # Deliver undelivered notifications
        undelivered_notifs = notification_repository.get_undelivered_notifications(user_key)
        for notif in undelivered_notifs:
            sio.emit('receive_notification', {'from_user_key': notif.get('from_user_key'), 'notification': notif['notification']}, room=sid)
            notification_repository.mark_as_delivered(notif['_id'])
    except UnauthorizedError as e:
        logging.warning(f"Socket connect failed: {str(e)}")
        return False

@sio.event
def disconnect(sid):
    for user_key, user_sid in list(connected_users.items()):
        if user_sid == sid:
            del connected_users[user_key]
            sio.emit('user_disconnected', {'user_key': user_key}, room=sid)
            logging.info(f"User {user_key} disconnected from socket {sid}")
            break

@sio.event
def send_message(sid, data):
    # data: {to_user_key, message, from_user_key}
    to_user_key = data.get('to_user_key')
    message = data.get('message')
    from_user_key = data.get('from_user_key')
    if to_user_key in connected_users:
        sio.emit('receive_message', {'from_user_key': from_user_key, 'message': message}, room=connected_users[to_user_key])
        # Optionally, mark as delivered in DB if you want to keep history
        message_repository.save_message(from_user_key, to_user_key, message, delivered=True)
    else:
        # Store message for offline delivery
        message_repository.save_message(from_user_key, to_user_key, message, delivered=False)
        logging.info(f"User {to_user_key} offline, message queued")

@sio.event
def broadcast_notification(sid, data):
    # data: {account_key, notification, from_user_key}
    account_key = data.get('account_key')
    notification = data.get('notification')
    from_user_key = data.get('from_user_key')
    # TODO: Lookup all user_keys for account_key (for now, broadcast to all connected users)
    for user_key, user_sid in connected_users.items():
        sio.emit('receive_notification', {'from_user_key': from_user_key, 'notification': notification}, room=user_sid)
        notification_repository.save_notification(account_key, user_key, notification, delivered=True)
    # For offline users, store notification for later delivery
    # You would need to fetch all user_keys for the account_key from your user repository
    # Example: offline_user_keys = ...
    # for user_key in offline_user_keys:
    #     if user_key not in connected_users:
    #         notification_repository.save_notification(account_key, user_key, notification, delivered=False)

# Flask app wrapper for socketio
application = socketio.WSGIApp(sio, app)
