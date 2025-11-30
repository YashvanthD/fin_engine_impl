import time
import random
import base64

from fin_server.security.authentication import AuthSecurity

def epoch_to_datetime(epoch):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(epoch))

def get_current_timestamp():
    return int(time.time())

def generate_key(length):
    return ''.join(random.choices('0123456789', k=length))

def build_user(data, account_key=None):
    user_data = data.copy()
    user_data['account_key'] = account_key if account_key else generate_key(6)
    from fin_server.repository.user_repository import mongo_db_repository
    from fin_server.routes.auth import default_subscription
    # If account_key is provided, try to fetch admin's subscription
    admin_subscription = None
    if account_key:
        admin_doc = mongo_db_repository.get_collection('users').find_one({
            'account_key': account_key,
            'roles': {'$in': ['admin']}
        })
        if admin_doc and 'subscription' in admin_doc:
            admin_subscription = admin_doc['subscription']
    while True:
        user_key = generate_key(9)
        if not mongo_db_repository.get_collection('users').find_one({'user_key': user_key}):
            break
    user_data['user_key'] = user_key
    user_data['permission_key'] = generate_key(9)
    user_data['joined_date'] = get_current_timestamp()
    # Use admin's subscription if available, else default
    user_data['subscription'] = admin_subscription if admin_subscription else default_subscription()
    if 'password' in user_data:
        user_data['password'] = base64.b64encode(user_data['password'].encode('utf-8')).decode('utf-8')
    refresh_payload = {
        'user_key': user_data['user_key'],
        'account_key': user_data['account_key'],
        'permission_key': user_data['permission_key'],
        'roles': user_data.get('roles', ['user']),
        'type': 'refresh'
    }
    refresh_token = AuthSecurity.create_refresh_token(refresh_payload)
    user_data['refresh_tokens'] = [refresh_token]
    return user_data

def build_refresh(user_data):
    refresh_payload = {
        'user_key': user_data['user_key'],
        'account_key': user_data['account_key'],
        'permission_key': user_data['permission_key'],
        'roles': user_data.get('roles', []),
        'type': 'refresh'
    }
    refresh_token = AuthSecurity.create_refresh_token(refresh_payload)
    return refresh_token
