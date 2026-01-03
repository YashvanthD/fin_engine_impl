import logging
from threading import Thread

from flask import request
from flask_socketio import SocketIO, emit, join_room, disconnect

from fin_server.repository.mongo_helper import get_collection
from fin_server.security.authentication import AuthSecurity

# Flask app should be passed in from server.py
socketio = SocketIO(async_mode='threading', cors_allowed_origins="*")


notification_queue_repo = get_collection('notification_queue')
user_repo = get_collection('users')

def authenticate_socket(token):
    try:
        payload = AuthSecurity.decode_token(token)
        return payload
    except Exception as e:
        logging.warning(f"Socket authentication failed: {e}")
        return None

@socketio.on('connect')
def handle_connect():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = authenticate_socket(token)
    if not payload:
        emit('error', {'error': 'Unauthorized'})
        disconnect()
        return
    user_key = payload.get('user_key')
    account_key = payload.get('account_key')
    join_room(user_key)
    join_room(account_key)
    emit('connected', {'message': 'Connected to notification service.'})
    # Send pending notifications
    pending = notification_queue_repo.get_pending(user_key=user_key)
    for n in pending:
        emit('notification', n, room=user_key)
        notification_queue_repo.mark_sent(n['_id'])

@socketio.on('send_notification')
def handle_send_notification(data):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = authenticate_socket(token)
    if not payload:
        emit('error', {'error': 'Unauthorized'})
        disconnect()
        return
    user_key = payload.get('user_key')
    # Accepts: {to_user_key, message, type}
    to_user_key = data.get('to_user_key')
    message = data.get('message')
    notif_type = data.get('type', 'info')
    notification = {
        'user_key': to_user_key,
        'from_user_key': user_key,
        'message': message,
        'type': notif_type
    }
    notification_queue_repo.enqueue(notification)
    emit('notification', notification, room=to_user_key)

@socketio.on('disconnect')
def handle_disconnect():
    pass

# Background worker to deliver pending notifications (for offline users)
def notification_worker():
    import time
    while True:
        # For all users with pending notifications, try to deliver
        pending = notification_queue_repo.get_pending()
        for n in pending:
            user_key = n.get('user_key')
            if user_key:
                socketio.emit('notification', n, room=user_key)
                notification_queue_repo.mark_sent(n['_id'])
        time.sleep(10)

def start_notification_worker():
    t = Thread(target=notification_worker, daemon=True)
    t.start()
